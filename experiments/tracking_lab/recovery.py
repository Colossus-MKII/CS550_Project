"""Local four-group retain/reset pilot. Start reading at execute().

python -m tracking_lab.recovery --check
python -m tracking_lab.recovery --output runs/recovery-local
No server, school connection, training, submission, or baseline overwrite.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
import traceback
import uuid

from . import ROOT, PACKAGE_ROOT, configure_runtime
from .common import digest, load_predictions, save_predictions, write_json
from .dataset import read_manifest, load_ground_truth
from .runtime import checked_weight, environment
from .recovery_events import resolve_events
from .recovery_metrics import evaluate_recovery


def assert_same_predictions(expected, actual):
    """Replay guard: adapter prefix must equal the previously verified baseline."""
    import numpy as np

    if len(expected) != len(actual):
        raise AssertionError("Baseline replay object count differs")
    for left, right in zip(
        sorted(expected, key=lambda x: x.identity),
        sorted(actual, key=lambda x: x.identity),
    ):
        assert (left.identity, left.category, left.score) == (
            right.identity,
            right.category,
            right.score,
        )
        np.testing.assert_array_equal(left.box, right.box)
        np.testing.assert_array_equal(left.mask, right.mask)


def execute(args):
    # 1. Freeze inputs, event routing, correction sources and provisional scoring.
    from .verify import verify
    from .recovery_engines import ByteEngine, SamEngine, Correction
    from .recovery_state import (
        sam_history_summary,
        state_digest,
        synchronized_sam_offload,
    )
    from .sam_baseline import run_sam

    config = json.loads(args.config.read_text(encoding="utf-8"))
    source = args.baseline.resolve()
    previous = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    baseline_verification = verify(source, args.data_root, args.trackeval_root)
    if baseline_verification["status"] != "passed":
        raise ValueError("Baseline not verified")
    base_config = previous["configuration"]
    ids = list(dict.fromkeys(spec["video_id"] for spec in config["events"]))
    videos, records, _ = read_manifest(args.data_root, ids)
    gt = {
        str(v.video_id): load_ground_truth(args.data_root, row)
        for v, row in zip(videos, records)
    }
    cache = {
        str(v.video_id): {
            m: load_predictions(source / str(v.video_id) / m)
            for m in ("YOLO", "A0", "B0")
        }
        for v in videos
    }
    events = resolve_events(config, base_config, gt, cache, source)
    configure_runtime()
    env = environment(args.device, config["seed"])
    sam_path, sam_sha = checked_weight("sam2.1_hiera_tiny.pt", args.weights_dir)
    if sam_sha != previous["weights"]["SAM"]["sha256"]:
        raise ValueError("SAM weight differs from baseline")
    if args.check:
        print(
            json.dumps(
                {
                    "status": "preflight_passed",
                    "device": env["device"],
                    "events": events,
                },
                indent=2,
            )
        )
        return None
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Choose a new output folder; old runs remain intact")
    output.mkdir(parents=True)
    summary = {
        "status": "running",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": env,
        "configuration": config,
        "baseline_configuration": base_config,
        "baseline_source": str(source),
        "baseline_summary_sha256": digest(source / "summary.json"),
        "baseline_files_sha256": {
            path.relative_to(source).as_posix(): digest(path)
            for video in videos
            for method in ("YOLO", "A0", "B0")
            for path in sorted((source / str(video.video_id) / method).glob("*"))
            if path.is_file() and path.suffix in {".npz", ".json"}
        },
        "data_root_relative_to_run": Path(
            os.path.relpath(args.data_root.resolve(), output)
        ).as_posix(),
        "sample_manifest_sha256": digest(args.data_root / "manifest.json"),
        "weights": previous["weights"],
        "events": events,
        "branches": [],
        "limitations": [
            "Development smoke pilot, not final protocol or held-out evidence.",
            "GT used for diagnostic target routing and separately labeled reference boxes.",
            "Source timestamps unknown: exported steps, not source seconds.",
            "A/B resets operate on different state types; compare within each pair first.",
        ],
    }
    write_json(output / "summary.json", summary)
    write_json(output / "events.json", events)
    write_json(output / "config.json", config)
    write_json(output / "baseline-verification.json", baseline_verification)
    snapshots = output / "code"
    snapshots.mkdir()
    for path in PACKAGE_ROOT.glob("*.py"):
        shutil.copyfile(path, snapshots / (path.name + ".txt"))
    summary["source_sha256"] = {p.name: digest(p) for p in PACKAGE_ROOT.glob("*.py")}
    started = time.perf_counter()
    print("Recovery output:", output, flush=True)
    predictor = None
    try:
        import numpy as np
        import torch
        from sam2.build_sam import build_sam2_video_predictor

        torch.cuda.reset_peak_memory_stats()
        predictor = build_sam2_video_predictor(
            "configs/sam2.1/sam2.1_hiera_t.yaml",
            str(sam_path),
            device=args.device,
            apply_postprocessing=True,
        )
        predictor.fill_hole_area = 0
        predictor.add_all_frames_to_correct_as_cond = True
        with torch.inference_mode(), torch.autocast(
            "cuda", dtype=torch.bfloat16
        ), synchronized_sam_offload(predictor):
            # The historical run used asynchronous CPU offload. Prompt-frame
            # display masks can race a GPU->CPU copy in the pinned upstream API.
            # Keep it untouched; build a synchronized native B0 reference FIRST.
            replay_root = output / "baseline_replay"
            differences = {}
            for video in videos:
                key = str(video.video_id)
                clean, log, stats = run_sam(
                    predictor, video, cache[key]["YOLO"], base_config
                )
                changed = []
                for frame, (old, new) in enumerate(zip(cache[key]["B0"], clean)):
                    try:
                        assert_same_predictions(old, new)
                    except AssertionError:
                        changed.append(frame)
                differences[key] = changed
                if previous.get("sam_cpu_offload_guard") and changed:
                    raise AssertionError(
                        f"Corrected baseline B0 inference is not repeatable: {key}, frames {changed}"
                    )
                cache[key]["B0"] = clean
                save_predictions(
                    replay_root / key / "B0", clean, (video.height, video.width)
                )
                write_json(replay_root / key / "B0/event-log.json", log)
                write_json(replay_root / key / "B0/run-stats.json", stats)
                (replay_root / key / "A0").mkdir(parents=True)
                shutil.copyfile(
                    source / key / "A0/state-trace.json",
                    replay_root / key / "A0/state-trace.json",
                )
            events = resolve_events(config, base_config, gt, cache, replay_root)
            summary["events"] = events
            summary["synchronized_reference"] = {
                "adapter": "CUDA synchronization after _run_single_frame_inference, before CPU interpolation",
                "historical_B0_different_frames": differences,
                "old_outputs_modified": False,
                "prefix_reference": "baseline_replay/*/B0; independent native run_sam replay with synchronized offload",
            }
            write_json(output / "events.json", events)
            write_json(output / "summary.json", summary)
            for event in events:
                if not event["eligible_common_state"]:
                    print(
                        "Ineligible:",
                        event["name"],
                        event["eligibility_reasons"],
                        flush=True,
                    )
                    continue
                key, t = str(event["video_id"]), event["frame"]
                video = next(v for v in videos if v.video_id == event["video_id"])
                a = ByteEngine(
                    base_config, config.get("byte_association_diagnostics", False)
                )
                b = SamEngine(predictor, video, base_config)
                prefixes, traces = {"A0": [], "B0": []}, {"A0": [], "B0": []}
                # 2. Run the shared, uncorrected prefix ONCE; replay against A0/B0.
                for frame in range(t):
                    for method, engine in (("A0", a), ("B0", b)):
                        objects, trace = engine.step(frame, cache[key]["YOLO"][frame])
                        try:
                            assert_same_predictions(cache[key][method][frame], objects)
                        except AssertionError as error:
                            raise AssertionError(
                                f"{event['name']} {method} prefix frame {frame}: "
                                f"expected {[(o.identity, o.category) for o in cache[key][method][frame]]}, "
                                f"actual {[(o.identity, o.category) for o in objects]}"
                            ) from error
                        prefixes[method].append(objects)
                        traces[method].append(trace)
                    if frame % 10 == 0:
                        print(event["name"], "prefix", frame, "/", t, flush=True)
                aid, bid = (event["anchors"][m]["prediction_id"] for m in ("A0", "B0"))
                if not (a.eligible(aid) and b.eligible(bid)):
                    raise AssertionError("Frozen eligibility disagrees with live state")
                event["prefix_exact_replay"] = True
                a_state = a.snapshot(a.find(aid)[1])
                prefix_hashes = {
                    "A0": state_digest(a_state),
                    "B0": sam_history_summary(b.state, bid)["sha256"],
                }
                # 3. Fork each SAME prefix. Freeze correction metadata within H/R.
                for condition in config["conditions"]:
                    if not event["condition_eligibility"][condition]:
                        continue
                    supplied = event["corrections"][condition]
                    for method, engine, identity in (("A0", a, aid), ("B0", b, bid)):
                        for reset in (False, True):
                            group = ("A" if method == "A0" else "B") + (
                                "-R" if reset else "-H"
                            )
                            branch = engine.fork()
                            branch_hash = (
                                state_digest(branch.snapshot(branch.find(identity)[1]))
                                if method == "A0"
                                else sam_history_summary(branch.state, identity)[
                                    "sha256"
                                ]
                            )
                            assert branch_hash == prefix_hashes[method]
                            skipped_step = None
                            if method == "B0" and config.get(
                                "sam_skip_next_refresh", False
                            ):
                                interval = base_config["discovery_interval"]
                                skipped_step = (t // interval + 1) * interval
                                branch.skip_refresh = (identity, skipped_step)
                            correction = Correction(
                                identity,
                                event["category"],
                                np.asarray(supplied["box"], np.float32),
                                supplied["score"],
                                supplied["detector_index"],
                                reset,
                            )
                            predictions, branch_trace = list(prefixes[method]), list(
                                traces[method]
                            )
                            # 4. One correction at t, then normal inputs only. No GT here.
                            for frame in range(t, t + config["window"] + 1):
                                objects, trace = branch.step(
                                    frame,
                                    cache[key]["YOLO"][frame],
                                    correction if frame == t else None,
                                )
                                predictions.append(objects)
                                branch_trace.append(trace)
                            folder = output / event["name"] / condition / group
                            save_predictions(
                                folder, predictions, (video.height, video.width)
                            )
                            write_json(folder / "state-trace.json", branch_trace)
                            # 5. Only the fixed designated ID is scored against its GT.
                            scores = evaluate_recovery(
                                gt[key][: len(predictions)],
                                predictions,
                                identity,
                                event["gt_id"],
                                t,
                                config["window"],
                                config["mask_iou_threshold"],
                                config["streak_required"],
                                branch_trace,
                            )
                            write_json(folder / "recovery.json", scores)
                            record = {
                                "event": event["name"],
                                "video_id": event["video_id"],
                                "condition": condition,
                                "group": group,
                                "prediction_id": identity,
                                "prefix_target_sha256": prefix_hashes[method],
                                "correction": supplied,
                                "folder": folder.relative_to(output).as_posix(),
                                "skipped_refresh_step": skipped_step,
                                **scores["summary"],
                            }
                            summary["branches"].append(record)
                            write_json(output / "summary.json", summary)
                            print(
                                "Completed",
                                event["name"],
                                condition,
                                group,
                                scores["summary"],
                                flush=True,
                            )
                            del branch
                            torch.cuda.empty_cache()
                # Check branch execution did not mutate either retained prefix.
                assert state_digest(a.snapshot(a.find(aid)[1])) == prefix_hashes["A0"]
                assert (
                    sam_history_summary(b.state, bid)["sha256"] == prefix_hashes["B0"]
                )
                del b, a
                torch.cuda.empty_cache()
        summary["status"] = "inference_completed"
        summary["peak_process_allocated_mib"] = (
            torch.cuda.max_memory_allocated() / 2**20
        )
        summary["wall_seconds"] = time.perf_counter() - started
        write_json(output / "summary.json", summary)
        print(
            "Inference complete. Next: python -m tracking_lab.recovery_report --output",
            output,
            flush=True,
        )
        return output
    except Exception:
        summary["status"], summary["error"] = "failed", traceback.format_exc()
        write_json(output / "summary.json", summary)
        raise
    finally:
        if predictor is not None:
            del predictor


def make_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--baseline", type=Path, default=ROOT / "runs/stage1-portable-20261017"
    )
    p.add_argument(
        "--config", type=Path, default=PACKAGE_ROOT / "defaults/recovery_pilot.json"
    )
    p.add_argument("--data-root", type=Path, default=ROOT / "data/stage1")
    p.add_argument("--weights-dir", type=Path, default=ROOT / "checkpoints")
    p.add_argument("--trackeval-root", type=Path, default=ROOT / "external/TrackEval")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--check", action="store_true")
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "runs"
        / (
            "recovery-"
            + datetime.now().strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:6]
        ),
    )
    return p


def main(argv=None):
    execute(make_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
