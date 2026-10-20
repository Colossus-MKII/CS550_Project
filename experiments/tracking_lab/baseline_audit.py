"""Compare immutable old/new baseline artifacts, without running either model.

This is an output-correctness audit, not a memory ablation. All annotation
access happens after inference. JSON uses run names, never host-private paths.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from .common import digest, load_predictions, mask_iou, write_json
from .dataset import load_ground_truth, read_manifest


def equal_frame(a, b):
    return len(a) == len(b) and all(
        x.identity == y.identity
        and x.category == y.category
        and x.score == y.score
        and np.array_equal(x.box, y.box)
        and np.array_equal(x.mask, y.mask)
        for x, y in zip(a, b)
    )


def audit(old, new, data_root, repeat=None, recovery=None, candidates=None):
    summary = json.loads((new / "summary.json").read_text(encoding="utf-8"))
    previous = json.loads((old / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] not in {"inference_and_scoring_completed", "completed"}:
        raise ValueError("Incomplete baseline")
    for field in ("configuration", "selection", "weights", "sample_manifest_sha256"):
        if previous[field] != summary[field]:
            raise ValueError("Correction audit requires identical " + field)
    if json.loads((old / "input-manifest.json").read_text()) != json.loads(
        (new / "input-manifest.json").read_text()
    ):
        raise ValueError("Correction audit requires identical input provenance")
    ids = summary["selection"]["video_ids"]
    videos, records, _ = read_manifest(data_root, ids)
    result = {
        "kind": "sam-cpu-offload-correction",
        "old_run": old.name,
        "new_run": new.name,
        "old_metrics_sha256": digest(old / "metrics.json"),
        "new_metrics_sha256": digest(new / "metrics.json"),
        "old_metrics": json.loads((old / "metrics.json").read_text()),
        "new_metrics": json.loads((new / "metrics.json").read_text()),
        "comparison": {},
        "examples": [],
        "scope": "Same inputs, weights and algorithm settings; CPU-read fence added. Not an H/R comparison.",
        "audit_source_sha256": digest(Path(__file__)),
        "inputs_weights_configuration_identical": True,
    }
    examples = {2686: (25, 1, 2), 2689: (25, 2, 1), 2718: (35, 2, 2)}
    for video, record in zip(videos, records):
        key = str(video.video_id)
        gt = load_ground_truth(data_root, record)
        predictions = {}
        row = {}
        for method in ("YOLO", "A0", "B0"):
            before = load_predictions(old / key / method)
            after = load_predictions(new / key / method)
            if len(before) != len(after):
                raise ValueError("Frame counts differ")
            changed = [
                t
                for t, (a, b) in enumerate(zip(before, after))
                if not equal_frame(a, b)
            ]
            row[method + "_changed_frames"] = changed
            if method != "B0" and changed:
                raise ValueError(
                    "A0/YOLO changed: this no longer isolates the SAM correction"
                )
            if repeat:
                other = load_predictions(repeat / key / method)
                if len(other) != len(after) or not all(
                    equal_frame(a, b) for a, b in zip(after, other)
                ):
                    raise ValueError(f"Full inference repeat differs: {key}/{method}")
            predictions[method] = (before, after)
        old_events = json.loads((old / key / "B0/event-log.json").read_text())
        new_events = json.loads((new / key / "B0/event-log.json").read_text())
        row["actions_and_active_ids_equal"] = all(
            a["actions"] == b["actions"] and a["active_ids"] == b["active_ids"]
            for a, b in zip(old_events, new_events)
        )
        row["changed_frames_are_prompt_steps"] = all(
            new_events[t]["detector_called"] for t in row["B0_changed_frames"]
        )
        row["frames"] = len(gt)
        result["comparison"][key] = row
        if video.video_id in examples:
            t, gt_id, pred_id = examples[video.video_id]
            truth = next(x for x in gt[t] if x.identity == gt_id)
            entry = {
                "video": video.video_id,
                "frame": t,
                "gt_id": gt_id,
                "prediction_id": pred_id,
            }
            for label, frames in zip(("old", "new"), predictions["B0"]):
                target = next((x for x in frames[t] if x.identity == pred_id), None)
                entry[label + "_mask_iou"] = (
                    mask_iou(truth.mask, target.mask) if target else 0.0
                )
            result["examples"].append(entry)
    result["changed_B0_frames"] = sum(
        len(r["B0_changed_frames"]) for r in result["comparison"].values()
    )
    result["total_frames"] = sum(r["frames"] for r in result["comparison"].values())
    result["full_inference_repeat"] = (
        {"status": "passed", "run": repeat.name}
        if repeat
        else {"status": "not_checked"}
    )
    if recovery:
        pilot = json.loads((recovery / "summary.json").read_text(encoding="utf-8"))
        verification = json.loads((recovery / "verification.json").read_text())
        repeated = json.loads((recovery / "repeat-verification.json").read_text())
        if (
            pilot["status"] != "completed"
            or verification["status"] != "passed"
            or repeated["status"] != "passed"
        ):
            raise ValueError("Recovery pilot not fully verified")
        result["recovery_pilot"] = {
            "run": recovery.name,
            "branches": len(pilot["branches"]),
            "status": "development_smoke_test_passed_not_formal_study",
        }
    if candidates:
        from .recovery_events import resolve_events

        config = json.loads(candidates.read_text(encoding="utf-8"))
        truth = {
            str(v.video_id): load_ground_truth(data_root, row)
            for v, row in zip(videos, records)
        }
        cache = {
            str(v.video_id): {
                m: load_predictions(new / str(v.video_id) / m)
                for m in ("YOLO", "A0", "B0")
            }
            for v in videos
        }
        result["next_candidates"] = {
            "status": "eligibility_checked_not_run_not_frozen",
            "configuration": config,
            "configuration_sha256": digest(candidates),
            "events": resolve_events(
                config, summary["configuration"], truth, cache, new
            ),
        }
    write_json(new / "correction-audit.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old", "new", "data-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--repeat", type=Path)
    parser.add_argument("--recovery", type=Path)
    parser.add_argument("--candidates", type=Path)
    args = parser.parse_args()
    result = audit(
        args.old, args.new, args.data_root, args.repeat, args.recovery, args.candidates
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "changed_B0_frames",
                    "total_frames",
                    "examples",
                    "full_inference_repeat",
                )
            },
            indent=2,
        )
    )
