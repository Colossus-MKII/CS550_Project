"""Run the frozen NATURAL failure supplement with the unchanged H/R engine.

1. Validate split, input and source fingerprints; create new per-event configs.
2. recovery.execute: native replay -> identical prefix -> four H/R groups.
3. recovery_report.build: independently rescore, audit reset, render videos.
4. Repeat the event named BEFORE outcomes; do not count it as a new sample.

No artificial history, prompt suppression, training, networking or publication.
"""

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import gc
from pathlib import Path
import shutil
import time
import traceback

from . import PACKAGE_ROOT
from .common import digest, write_json
from .natural_events import read_json
from .recovery_cohort import INFERENCE_FILES


def prepare(frozen_path, output):
    """Reject a changed split, changed baselines, held-out IDs or old output."""
    frozen_path, output = Path(frozen_path), Path(output)
    if output.exists():
        raise FileExistsError("Never overwrite or resume a completed/partial cohort")
    frozen = read_json(frozen_path)
    if not frozen["events"]:
        raise ValueError("No eligible natural events; do not manufacture failures")
    if digest(frozen["split_path"]) != frozen["split_sha256"]:
        raise ValueError("Frozen split changed")
    if digest(frozen["queue_path"]) != frozen["queue_sha256"]:
        raise ValueError("Development queue changed")
    development = {r["video_id"] for r in read_json(frozen["split_path"])["splits"]["development"]}
    data_root = Path(frozen["data_root"])
    if digest(data_root / "manifest.json") != frozen["data_manifest_sha256"]:
        raise ValueError("Data manifest changed")
    if digest(PACKAGE_ROOT / "natural_events.py") != frozen["selection_source_sha256"]:
        raise ValueError("Selection code differs from frozen scan")
    if len({e["video_id"] for e in frozen["events"]}) != len(frozen["events"]):
        raise ValueError("At most one supplementary event per video")
    for e in frozen["events"]:
        if e["video_id"] not in development or e["video_id"] == 2967:
            raise ValueError("Held-out or excluded boundary video")
        if "persistent_failure" not in e["labels"].values():
            raise ValueError("Supplement must contain a native persistent failure")
        if digest(Path(e["baseline_folder"]) / "summary.json") != e["baseline_summary_sha256"]:
            raise ValueError("Native baseline changed after selection")
    output.mkdir(parents=True)
    shutil.copyfile(frozen_path, output / "frozen-events.json")
    base = read_json(PACKAGE_ROOT / "defaults/recovery_long_normal.json")
    records = []
    for e in frozen["events"]:
        config = {
            **base,
            "role": "natural_persistent_failure_supplement_local3080_no_artificial_history",
            "frozen_selection_sha256": digest(frozen_path),
            "events": [{k: e[k] for k in ("name", "video_id", "gt_id", "category", "frame")}],
        }
        config_path = output / "configs" / (e["name"] + ".json")
        write_json(config_path, config)
        records.append({
            "event_id": e["event_id"], "name": e["name"], "video_id": e["video_id"],
            "scene": e["scene"], "labels": e["labels"],
            "baseline": e["baseline_folder"], "baseline_summary_sha256": e["baseline_summary_sha256"],
            "config_file": str(config_path.resolve()), "config_sha256": digest(config_path),
            "status": "prepared",
        })
    plan = {
        "status": "prepared", "created_utc": datetime.now(timezone.utc).isoformat(),
        "authorization": frozen["authorization"],
        "frozen_selection_sha256": digest(frozen_path), "split_sha256": frozen["split_sha256"],
        "data_root": str(data_root), "conditions": ["yolo", "reference"],
        "groups": ["A-H", "A-R", "B-H", "B-R"], "window": 30,
        "report_windows": [8,20,30], "expected_branches": 8*len(records),
        "events": records, "repeat_event_id": frozen["repeat_event_id"],
        "inference_source_sha256": {n: digest(PACKAGE_ROOT / n) for n in
                                    (*INFERENCE_FILES, "natural_events.py", "natural_recovery.py")},
    }
    write_json(output / "cohort.json", plan)
    return plan


def execute(frozen_path, output):
    """Local GPU only. Every branch is verified; old runs are never mutated."""
    import torch
    from .recovery import execute as run, make_parser
    from .recovery_report import build
    from .recovery_repeat import compare

    if not torch.cuda.is_available() or "3080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("Natural follow-up is restricted to the LOCAL RTX 3080")
    output = Path(output)
    plan = prepare(frozen_path, output)
    plan.update(status="running", device=torch.cuda.get_device_name(0))
    write_json(output / "cohort.json", plan)
    started = time.perf_counter()

    def run_one(row, destination, log_name):
        for n, sha in plan["inference_source_sha256"].items():
            if digest(PACKAGE_ROOT / n) != sha:
                raise ValueError("Inference source changed during batch: " + n)
        if digest(row["config_file"]) != row["config_sha256"]:
            raise ValueError("Frozen config changed")
        args = make_parser().parse_args([
            "--baseline", row["baseline"], "--config", row["config_file"],
            "--data-root", plan["data_root"], "--device", "cuda:0", "--output", str(destination)
        ])
        with (output / log_name).open("w", encoding="utf-8") as stream, redirect_stdout(stream), redirect_stderr(stream):
            run(args)
            verification = build(destination, Path(plan["data_root"]))
        summary = read_json(destination / "summary.json")
        if len(summary["branches"]) != 8 or not summary["events"][0].get("prefix_exact_replay"):
            raise AssertionError("Require 8 branches and exact native prefixes")
        if any(summary["synchronized_reference"]["historical_B0_different_frames"].values()):
            raise AssertionError("Native B0 changed since event selection")
        gc.collect()
        torch.cuda.empty_cache()
        return verification

    try:
        for i, row in enumerate(plan["events"], 1):
            print(f"Natural event {i}/{len(plan['events'])}: {row['name']} {row['labels']}", flush=True)
            destination = output / "events" / row["name"]
            verification = run_one(row, destination, row["name"] + ".log")
            row.update(status="completed", folder=str(destination.resolve()), branches=8,
                       verification=verification, summary_sha256=digest(destination / "summary.json"))
            write_json(output / "cohort.json", plan)
            print(row["event_id"], "8 branches verified and 2 videos rendered", flush=True)
        repeated = next(e for e in plan["events"] if e["event_id"] == plan["repeat_event_id"])
        destination = output / "repeat" / repeated["name"]
        print("Independent repeat, preselected:", repeated["event_id"], flush=True)
        run_one(repeated, destination, "repeat-" + repeated["name"] + ".log")
        repeat_check = compare(Path(repeated["folder"]), destination)
        repeat_check["event_id"] = repeated["event_id"]
        write_json(output / "repeat-verification.json", repeat_check)
        plan.update(status="completed", actual_branches=sum(e["branches"] for e in plan["events"]),
                    repeat_branches=8, wall_seconds=time.perf_counter()-started,
                    repeat_verification=repeat_check)
        write_json(output / "cohort.json", plan)
        print("Completed", plan["actual_branches"], "main branches + 8 repeat-only branches", flush=True)
    except Exception:
        plan.update(status="failed_preserved", error=traceback.format_exc())
        write_json(output / "cohort.json", plan)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frozen", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    execute(a.frozen, a.output)


if __name__ == "__main__":
    main()
