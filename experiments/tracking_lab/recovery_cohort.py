"""Run the approved 16-event cohort using the existing four-group engine.

Learning map:
  prepare_plan(): reviewed JSON -> pinned per-event configs/baseline paths.
  execute():      each config -> recovery.execute() -> read-only verification.
  render():       saved masks -> recovery_report.build() -> comparison MP4s.

Every event has the same 30-step protocol, both correction-box sources, and
A-H/A-R/B-H/B-R. BC01/2967 is explicitly excluded. No training, networking,
website update or baseline overwrite. A fresh output root is mandatory.
"""

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import shutil
import time
import traceback

from . import PACKAGE_ROOT
from .common import digest, write_json
from .recovery_events import resolve_events
from .dataset import read_manifest, load_ground_truth
from .common import load_predictions


INFERENCE_FILES = (
    "recovery.py",
    "recovery_events.py",
    "recovery_engines.py",
    "recovery_state.py",
    "recovery_metrics.py",
    "association_trace.py",
    "sam_io.py",
    "sam_baseline.py",
    "bytetrack.py",
    "common.py",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prepare_plan(review_path, baselines, data_root, output):
    """Validate EVERY reviewed route before model inference starts.

    Authorization is recorded in a new execution plan; the frozen review JSON
    remains awaiting-review/approved=False as historical evidence, untouched.
    """
    review_path, baselines, data_root, output = map(
        Path, (review_path, baselines, data_root, output)
    )
    if output.exists():
        raise FileExistsError(
            "Use a NEW cohort output; no resume/overwrite of old runs"
        )
    review = read_json(review_path)
    if len(review["events"]) != 16 or {e["event_id"] for e in review["events"]} != {
        f"E{i:02d}" for i in range(1, 17)
    }:
        raise ValueError("Expected the reviewed 16 primary events only")
    if any(e["video_id"] == 2967 for e in review["events"]):
        raise ValueError("2967 is a boundary case, never run it in this batch")
    if len({e["video_id"] for e in review["events"]}) != 16:
        raise ValueError("One primary event per video")
    base = read_json(PACKAGE_ROOT / "defaults/recovery_long_normal.json")
    records = []
    for selected in review["events"]:
        identity = selected["video_id"]
        source = baselines / str(identity)
        previous = read_json(source / "summary.json")
        if source.resolve() != Path(selected["baseline_folder"]).resolve():
            raise ValueError("Baseline folder changed from review")
        if previous["status"] not in {"inference_and_scoring_completed", "completed"}:
            raise ValueError("Incomplete baseline")
        if "3080" not in previous["environment"]["device"]:
            raise ValueError("Only local RTX 3080 baseline inputs are allowed")
        name = f"{selected['event_id']}-{selected['scene']}-{identity}-GT{selected['gt_id']}-t{selected['frame']}"
        spec = {k: selected[k] for k in ("video_id", "gt_id", "category", "frame")}
        spec.update(
            name=name,
            purpose=selected["rationale_zh"],
            reviewed_event_id=selected["event_id"],
            scene=selected["scene"],
        )
        config = {
            **base,
            "role": "approved_16_primary_events_local3080_normal_refresh",
            "review_sha256": digest(review_path),
            "events": [spec],
        }
        videos, rows, _ = read_manifest(data_root, [identity])
        gt = {str(identity): load_ground_truth(data_root, rows[0])}
        cache = {
            str(identity): {
                m: load_predictions(source / str(identity) / m)
                for m in ("YOLO", "A0", "B0")
            }
        }
        resolved = resolve_events(config, previous["configuration"], gt, cache, source)[
            0
        ]
        if not resolved["eligible_common_state"] or not all(
            resolved["condition_eligibility"].values()
        ):
            raise ValueError(f"Review eligibility changed: {name}")
        if resolved["anchors"] != selected["anchors"] or resolved["corrections"][
            "yolo"
        ] != {k: v for k, v in selected["yolo_correction"].items() if k != "box_iou"}:
            raise ValueError(f"Frozen routing/correction changed: {name}")
        if (
            resolved["corrections"]["reference"]["box"]
            != selected["reference_correction"]["box"]
        ):
            raise ValueError("Reviewed reference box changed")
        t = selected["frame"]
        visibility = [
            any(o.identity == selected["gt_id"] for o in frame)
            for frame in gt[str(identity)][t + 1 : t + 31]
        ]
        if sum(visibility) != selected["visible_followup"]:
            raise ValueError("GT observability differs from reviewed event")
        records.append(
            {
                "event_id": selected["event_id"],
                "name": name,
                "video_id": identity,
                "scene": selected["scene"],
                "config": config,
                "baseline": str(source.resolve()),
                "baseline_summary_sha256": digest(source / "summary.json"),
                "anchors": resolved["anchors"],
                "corrections": resolved["corrections"],
                "reviewed_visible_steps": sum(visibility),
                "status": "prepared",
            }
        )
    output.mkdir(parents=True)
    for row in records:
        config_file = output / "configs" / f"{row['name']}.json"
        write_json(config_file, row.pop("config"))
        row["config_file"] = str(config_file.resolve())
        row["config_sha256"] = digest(config_file)
    shutil.copyfile(review_path, output / "reviewed-events.json")
    plan = {
        "status": "prepared",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "authorization": "User explicitly requested running the v3 16-event primary list; keep 2967 unrun.",
        "review_sha256": digest(review_path),
        "split_sha256": review["split_sha256"],
        "queue_sha256": review["queue_sha256"],
        "boundary_cases_run": False,
        "expected_primary_events": 16,
        "expected_branches": 128,
        "conditions": ["yolo", "reference"],
        "groups": ["A-H", "A-R", "B-H", "B-R"],
        "window": 30,
        "report_windows": [8, 20, 30],
        "sam_skip_next_refresh": False,
        "logical_device": "cuda:0",
        "events": records,
        "data_root": str(data_root.resolve()),
        "data_manifest_sha256": digest(data_root / "manifest.json"),
        "inference_source_sha256": {
            n: digest(PACKAGE_ROOT / n) for n in INFERENCE_FILES
        },
    }
    write_json(output / "cohort.json", plan)
    return plan


def execute(review, baselines, data_root, output):
    """One reviewed event per archive; failure stops without deleting anything."""
    import torch
    from .recovery import execute as run_recovery, make_parser
    from .recovery_report import verify_recovery

    if not torch.cuda.is_available() or "3080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("This batch is restricted to the LOCAL RTX 3080")
    output = Path(output)
    plan = prepare_plan(review, baselines, data_root, output)
    plan["device"] = torch.cuda.get_device_name(0)
    plan["status"] = "running"
    write_json(output / "cohort.json", plan)
    started = time.perf_counter()
    try:
        for index, row in enumerate(plan["events"], 1):
            for name, sha in plan["inference_source_sha256"].items():
                if digest(PACKAGE_ROOT / name) != sha:
                    raise ValueError(
                        "Inference code changed during the frozen cohort: " + name
                    )
            if digest(row["config_file"]) != row["config_sha256"]:
                raise ValueError("Frozen event config changed")
            print("Cohort", index, "/16", row["name"], flush=True)
            destination = output / "events" / row["name"]
            args = make_parser().parse_args(
                [
                    "--baseline",
                    row["baseline"],
                    "--config",
                    row["config_file"],
                    "--data-root",
                    str(data_root),
                    "--device",
                    "cuda:0",
                    "--output",
                    str(destination),
                ]
            )
            with (output / f"{row['name']}.log").open(
                "w", encoding="utf-8"
            ) as stream, redirect_stdout(stream), redirect_stderr(stream):
                run_recovery(args)
                summary, _, _, _, checks = verify_recovery(destination, Path(data_root))
            if len(summary["branches"]) != 8 or not summary["events"][0].get(
                "prefix_exact_replay"
            ):
                raise AssertionError(
                    "Expected all eight verified, prefix-identical branches"
                )
            row.update(
                status="inference_and_score_verification_completed",
                folder=str(destination.resolve()),
                branches=len(summary["branches"]),
                verification=checks,
                summary_sha256=digest(destination / "summary.json"),
            )
            write_json(destination / "cohort-verification.json", checks)
            write_json(output / "cohort.json", plan)
            gc.collect()
            torch.cuda.empty_cache()
            print(row["name"], "8 branches verified", flush=True)
        plan["status"] = "inference_completed"
        plan["actual_branches"] = sum(e["branches"] for e in plan["events"])
        plan["wall_seconds"] = time.perf_counter() - started
        write_json(output / "cohort.json", plan)
        print("Cohort complete: 128 branches; 2967 NOT run", flush=True)
    except Exception:
        plan["status"] = "failed_preserved"
        plan["error"] = traceback.format_exc()
        write_json(output / "cohort.json", plan)
        raise


def render(output):
    """Render only newly created runs; never touch the baseline archives."""
    from .recovery_report import build

    output = Path(output)
    plan = read_json(output / "cohort.json")
    if plan["status"] != "inference_completed":
        raise ValueError("Render only a complete 128-branch cohort")
    for row in plan["events"]:
        print("Render", row["name"], flush=True)
        build(Path(row["folder"]), Path(plan["data_root"]))
        row["status"] = "completed"
        row["summary_sha256"] = digest(Path(row["folder"]) / "summary.json")
        write_json(output / "cohort.json", plan)
    plan["status"] = "completed"
    write_json(output / "cohort.json", plan)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("run", "render"))
    for name in ("review", "baselines", "data-root", "output"):
        p.add_argument("--" + name, type=Path, required=name == "output")
    args = p.parse_args(argv)
    if args.action == "run":
        execute(args.review, args.baselines, args.data_root, args.output)
    else:
        render(args.output)


if __name__ == "__main__":
    main()
