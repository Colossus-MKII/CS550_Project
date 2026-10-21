"""Select NATURAL persistent failures from saved development baselines only.

Reading order: fixed_id_curve -> failure_label -> scan -> choose_events.
No H/R output is opened here. No model is imported, trained or poisoned.
The frozen JSON is written BEFORE the new H/R batch starts, not retrospectively.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from .common import digest, load_predictions, mask_iou, write_json
from .dataset import read_manifest, load_ground_truth
from .selection_preflight import inspect_event


POLICY = {
    "threshold": 0.5,
    "consecutive_failure_steps": 3,
    "earlier_consecutive_correct_steps": 3,
    "window": 30,
    "followup_visibility": "all_30_visible",
    "conditions": ["yolo", "reference"],
    "max_events_per_video": 1,
    "requested_failure_events_per_model": 4,
    "exclude_video_ids": [2967],
    "selection_order": "B failures then A failures; unused videos first, then video_id/frame/gt_id; at most 4 per selecting model",
    "outcome_information": "native prefix only; future GT visibility only; NEVER H/R or future native prediction scores",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def has_correct_run(values, length=3):
    streak = 0
    for value in values:
        streak = streak + 1 if value is not None and value >= 0.5 else 0
        if streak >= length:
            return True
    return False


def failure_label(values, t):
    """Consecutive exported steps: invisible GT NEVER counts as failure.

    A past correct streak must precede the three failing steps. The ID is not
    reassigned when predictions become poor or another ID follows the target.
    """
    tail = values[t - 2 : t + 1] if t >= 2 else []
    if len(tail) != 3 or any(v is None for v in tail):
        return "insufficient_visible_prefix"
    if all(v < 0.5 for v in tail) and has_correct_run(values[: t - 2]):
        return "persistent_failure"
    if all(v >= 0.5 for v in tail):
        return "maintenance"
    return "transient_failure" if tail[-1] < 0.5 else "recently_unstable"


def fixed_id_curve(gt, predictions, gt_id, category):
    """First IoU-qualified prefix ID, identical tie-break to anchor_identity()."""
    pid, anchor = None, None
    values = []
    for t, objects in enumerate(gt):
        truth = next((o for o in objects if o.identity == gt_id), None)
        if truth is None:
            values.append(None)
            continue
        if pid is None:
            matches = [
                (mask_iou(truth.mask, o.mask), o.identity)
                for o in predictions[t] if o.category == category
            ]
            quality, identity = max(matches, default=(0.0, None))
            if quality >= 0.5:
                pid, anchor = identity, t
        found = next((o for o in predictions[t] if o.identity == pid), None)
        values.append(
            mask_iou(truth.mask, found.mask)
            if found is not None and found.category == category else 0.0
        )
    return values, pid, anchor


def choose_events(candidates, previous_videos, per_model=4):
    """Deterministic quota, no ranking by recovery outcome or prompt quality.

    One video is one new event. If both systems fail, its labels retain BOTH
    failures, but selection quotas do not force an artificial balanced grid.
    """
    selected, used = [], set()
    ordered = sorted(candidates, key=lambda r: (
        r["video_id"] in previous_videos, r["video_id"], r["frame"], r["gt_id"]
    ))
    for model in ("B0", "A0"):
        count = 0
        for row in ordered:
            if row["video_id"] in used or row["labels"][model] != "persistent_failure":
                continue
            selected.append({**row, "selected_for_model": model})
            used.add(row["video_id"])
            count += 1
            if count == per_model:
                break
    for i, row in enumerate(selected, 1):
        row["event_id"] = f"N{i:02d}"
        row["name"] = f"N{i:02d}-natural-{row['video_id']}-GT{row['gt_id']}-t{row['frame']}"
        row["scene"] = "natural_persistent_failure"
    return selected


def scan(queue_path, split_path, baselines, data_root, previous_path, output):
    """1. Scan native baselines. 2. Save full audit. 3. Freeze selected events."""
    queue_path, split_path, baselines, data_root, previous_path, output = map(
        Path, (queue_path, split_path, baselines, data_root, previous_path, output)
    )
    if output.exists():
        raise FileExistsError("New selection folder required; old manifests stay frozen")
    queue, split = read_json(queue_path), read_json(split_path)
    development = {r["video_id"] for r in split["splits"]["development"]}
    if queue["split_sha256"] != digest(split_path) or not set(queue["video_ids"]) <= development:
        raise ValueError("Only the frozen development queue may be screened")
    previous_videos = {e["video_id"] for e in read_json(previous_path)["events"]}
    output.mkdir(parents=True)
    policy = {**POLICY, "frozen_utc": datetime.now(timezone.utc).isoformat()}
    write_json(output / "policy.json", policy)  # Written before scanning outcomes.
    candidates, audit = [], []
    for vid in sorted(queue["video_ids"]):
        if vid in POLICY["exclude_video_ids"]:
            audit.append({"video_id": vid, "status": "excluded_existing_boundary"})
            continue
        source = baselines / str(vid)
        summary = read_json(source / "summary.json")
        if summary["status"] != "inference_and_scoring_completed" or not summary.get("sam_cpu_offload_guard"):
            raise ValueError(f"Require corrected completed native baseline: {vid}")
        _, rows, _ = read_manifest(data_root, [vid])
        gt = load_ground_truth(data_root, rows[0])
        folder = source / str(vid)
        predictions = {m: load_predictions(folder / m) for m in ("YOLO", "A0", "B0")}
        trace, log = read_json(folder / "A0/state-trace.json"), read_json(folder / "B0/event-log.json")
        tracks = sorted({(o.identity, o.category) for objects in gt for o in objects})
        accepted, rejected = [], Counter()
        for gid, category in tracks:
            curves = {m: fixed_id_curve(gt, predictions[m], gid, category)[0] for m in ("A0", "B0")}
            found_for = set()
            for t in range(5, len(gt) - 30):
                labels = {m: failure_label(curves[m], t) for m in curves}
                failing = {m for m in curves if labels[m] == "persistent_failure"} - found_for
                if not failing:
                    continue
                if not all(has_correct_run(curves[m][:t-2]) for m in curves):
                    rejected["other_system_no_earlier_three_correct"] += 1
                    continue
                if not all(any(o.identity == gid for o in gt[s]) for s in range(t, t+31)):
                    rejected["incomplete_30_step_GT_visibility"] += 1
                    continue
                row = inspect_event(gt, predictions, trace, log, summary["configuration"],
                                    {"video_id": vid, "gt_id": gid, "category": category, "frame": t})
                if not row["eligible_common_state"] or row["yolo_correction"] is None:
                    rejected["common_state_or_YOLO_box_unavailable"] += 1
                    continue
                row.update(
                    labels=labels,
                    recent_three_iou={m: curves[m][t-2:t+1] for m in curves},
                    baseline_folder=str(source.resolve()),
                    baseline_summary_sha256=digest(source / "summary.json"),
                    reused_video_from_16=vid in previous_videos,
                    visible_followup=30,
                )
                # inspect_event exposes native future actions for diagnostics.
                # They are deliberately removed from the selection manifest.
                row.pop("B0_future_target_actions", None)
                candidates.append(row)
                accepted.append({"gt_id": gid, "frame": t, "labels": labels})
                found_for |= failing
                if len(found_for) == 2:
                    break
        audit.append({"video_id": vid, "status": "screened", "candidate_events": accepted,
                      "rejected_trigger_steps": dict(rejected)})
        write_json(output / "scan-progress.json", {"videos": audit})
        print("Natural scan", vid, "eligible", len(accepted), flush=True)
    selected = choose_events(candidates, previous_videos)
    write_json(output / "candidates.json", {"events": candidates, "audit": audit})
    frozen = {
        "schema": 1,
        "status": "algorithmically_frozen_before_new_HR_not_human_reviewed",
        "authorization": "User: 那把后续实验做了; natural-failure follow-up only, local RTX3080",
        "policy": policy,
        "policy_sha256": digest(output / "policy.json"),
        "split_path": str(split_path.resolve()), "split_sha256": digest(split_path),
        "queue_path": str(queue_path.resolve()), "queue_sha256": digest(queue_path),
        "data_root": str(data_root.resolve()), "data_manifest_sha256": digest(data_root / "manifest.json"),
        "previous_event_manifest_sha256": digest(previous_path),
        "selection_source_sha256": digest(Path(__file__)),
        "candidate_count": len(candidates),
        "events": selected,
        "repeat_event_id": selected[0]["event_id"] if selected else None,
        "limitations": [
            "Outcome-enriched development sample; not natural failure prevalence or held-out evaluation.",
            "Natural prefix quality is observed, not experimentally manipulated history reliability.",
            "Reference/YOLO sources are not guaranteed ordered prompt quality levels.",
            "Reused videos are correlated with earlier cohorts; never pool as new independent recordings.",
        ],
    }
    write_json(output / "frozen-events.json", frozen)
    print(json.dumps({"selected": [(r["event_id"], r["video_id"], r["gt_id"], r["frame"], r["labels"]) for r in selected]}), flush=True)
    return frozen


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("queue", "split", "baselines", "data-root", "previous", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args(argv)
    scan(a.queue, a.split, a.baselines, a.data_root, a.previous, a.output)


if __name__ == "__main__":
    main()
