"""READ-ONLY event eligibility checks against automatic development baselines.

No interventions are executed. The first IoU-qualified prefix ID stays fixed;
the catalog is a selection aid, not H/R results or proof of causal mechanisms.
Run again to add newly completed videos, without replacing prior per-video files.
"""

import argparse
import json
from pathlib import Path

from .common import box_iou, digest, load_predictions, mask_iou, write_json
from .dataset import load_ground_truth, read_manifest
from .recovery_events import anchor_identity


def inspect_event(gt, predictions, trace, log, config, row):
    """Same routing/state criteria as recovery_events, plus descriptive checks."""
    t, identity, category = row["frame"], row["gt_id"], row["category"]
    truth = next(o for o in gt[t] if o.identity == identity)
    reasons, anchors, prefix_quality, states = [], {}, {}, {}
    for method in ("A0", "B0"):
        anchor = anchor_identity(gt, predictions[method], identity, category, t, 0.5)
        anchors[method] = anchor
        if anchor is None:
            reasons.append(method + ": no prefix identity anchor")
            prefix_quality[method] = {"qualified_frames": 0}
            continue
        pid = anchor["prediction_id"]
        samples = []
        for step in range(t):
            target = next((o for o in gt[step] if o.identity == identity), None)
            output = next(
                (o for o in predictions[method][step] if o.identity == pid), None
            )
            if target:
                samples.append(mask_iou(target.mask, output.mask) if output else 0.0)
        prefix_quality[method] = {
            "qualified_frames": sum(i >= 0.5 for i in samples),
            "visible_frames": len(samples),
            "mean_fixed_id_iou": sum(samples) / max(1, len(samples)),
        }
        if method == "A0":
            state = next((s for s in trace[t - 1]["states"] if s["id"] == pid), None)
            states[method] = state
            if not state or not state["activated"]:
                reasons.append("A0: no initialized retained state")
        else:
            accepted = [
                entry["frame"]
                for entry in log[:t]
                for action in entry["actions"]
                if action.get("id") == pid
                and action["action"] in {"refresh", "discover"}
            ]
            states[method] = {
                "active_at_previous_step": pid in log[t - 1]["active_ids"],
                "last_accepted_prompt": max(accepted) if accepted else None,
            }
            if pid not in log[t - 1]["active_ids"]:
                reasons.append("B0: designated state already deleted")
            if not accepted or t - max(accepted) > config["sam_retention_steps"]:
                reasons.append("B0: designated state expires before correction")
    detections = [o for o in predictions["YOLO"][t] if o.category == category]
    usable = [
        o
        for o in detections
        if o.score >= config["sam_prompt_conf"] and box_iou(o.box, truth.box) >= 0.3
    ]
    detection = max(
        usable, key=lambda o: (box_iou(o.box, truth.box), o.score), default=None
    )
    current = {}
    for method, anchor in anchors.items():
        output = next(
            (
                o
                for o in predictions[method][t]
                if anchor and o.identity == anchor["prediction_id"]
            ),
            None,
        )
        current[method] = mask_iou(truth.mask, output.mask) if output else 0.0
    return {
        **row,
        "anchors": anchors,
        "prefix_quality": prefix_quality,
        "retained_states": states,
        "eligibility_reasons": reasons,
        "eligible_common_state": not reasons,
        "strong_prefix_both_ge3": all(
            v["qualified_frames"] >= 3 for v in prefix_quality.values()
        ),
        "yolo_correction": (
            {
                "detector_index": detection.identity,
                "box": detection.box.tolist(),
                "score": detection.score,
                "box_iou": box_iou(detection.box, truth.box),
            }
            if detection
            else None
        ),
        "reference_correction": {"box": truth.box.tolist()},
        "yolo_overlapping_boxes_iou_ge_01": [
            {
                "detector_index": o.identity,
                "score": o.score,
                "box_iou": box_iou(o.box, truth.box),
            }
            for o in detections
            if box_iou(o.box, truth.box) >= 0.1
        ],
        "baseline_fixed_id_mask_iou_at_correction": current,
        "B0_future_target_actions": [
            {"frame": e["frame"], **a}
            for e in log[t + 1 : t + 31]
            for a in e["actions"]
            if anchors["B0"] and a.get("id") == anchors["B0"]["prediction_id"]
        ],
    }


def catalog(queue_path, data_root, gt_screen, baselines, output):
    queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    features_path = Path(gt_screen) / "gt-features.json"
    rows = json.loads(features_path.read_text(encoding="utf-8"))["rows"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    completed, pending = [], []
    for identity in queue["video_ids"]:
        destination = output / f"{identity}.json"
        if destination.exists():
            previous = json.loads(destination.read_text(encoding="utf-8"))
            if previous["queue_sha256"] != digest(queue_path):
                raise ValueError("Catalog belongs to another frozen queue")
            completed.append(identity)
            continue
        source = Path(baselines) / str(identity)
        if not (source / "summary.json").exists():
            pending.append(identity)
            continue
        summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
        if summary["status"] != "inference_and_scoring_completed":
            pending.append(identity)
            continue
        _, records, _ = read_manifest(data_root, [identity])
        gt = load_ground_truth(data_root, records[0])
        folder = source / str(identity)
        predictions = {
            name: load_predictions(folder / name) for name in ("YOLO", "A0", "B0")
        }
        trace = json.loads((folder / "A0/state-trace.json").read_text(encoding="utf-8"))
        log = json.loads((folder / "B0/event-log.json").read_text(encoding="utf-8"))
        result = [
            inspect_event(gt, predictions, trace, log, summary["configuration"], row)
            for row in rows
            if row["video_id"] == identity
        ]
        write_json(
            destination,
            {
                "video_id": identity,
                "purpose": "READ_ONLY_baseline_event_preflight_NOT_HR",
                "queue_sha256": digest(queue_path),
                "gt_features_sha256": digest(features_path),
                "baseline_summary_sha256": digest(source / "summary.json"),
                "baseline_folder": str(source.resolve()),
                "source_sha256": digest(Path(__file__)),
                "H_R_runs": 0,
                "events": result,
            },
        )
        completed.append(identity)
        print("Preflight", identity, len(result), "events", flush=True)
    print(json.dumps({"completed": completed, "pending": pending}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queue", "data-root", "gt-screen", "baselines", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    catalog(args.queue, args.data_root, args.gt_screen, args.baselines, args.output)


if __name__ == "__main__":
    main()
