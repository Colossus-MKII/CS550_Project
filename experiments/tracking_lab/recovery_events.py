"""Freeze diagnostic event routing BEFORE inspecting any H/R outcomes.

GT is deliberately used here for target routing and the reference-box condition.
This is a controlled mechanism study, NOT an automatic re-identification claim.
The fixed prediction ID is first anchored in the PREFIX, never reselected later.
"""

import json
from .common import box_iou, mask_iou


def anchor_identity(gt, predictions, gt_id, category, stop, threshold):
    for t in range(stop):
        truth = next((x for x in gt[t] if x.identity == gt_id), None)
        if truth is None:
            continue
        candidates = [
            (mask_iou(truth.mask, x.mask), x.identity)
            for x in predictions[t]
            if x.category == category
        ]
        if candidates:
            quality, identity = max(candidates)
            if quality >= threshold:
                return {
                    "prediction_id": identity,
                    "anchor_frame": t,
                    "anchor_iou": quality,
                }
    return None


def resolve_events(config, videos, ground_truth, cache, source):
    events = []
    for spec in config["events"]:
        key, t = str(spec["video_id"]), spec["frame"]
        gt = ground_truth[key]
        row = {
            **spec,
            "window": config["window"],
            "anchors": {},
            "eligibility_reasons": [],
        }
        if t < 1 or t + config["window"] >= len(gt):
            row["eligibility_reasons"].append("insufficient prefix or future window")
        truth = next((x for x in gt[t] if x.identity == spec["gt_id"]), None)
        if truth is None or truth.category != spec["category"]:
            row["eligibility_reasons"].append(
                "designated GT not visible with specified class at correction"
            )
        for method in ("A0", "B0"):
            anchor = anchor_identity(
                gt,
                cache[key][method],
                spec["gt_id"],
                spec["category"],
                t,
                config["anchor_mask_iou"],
            )
            row["anchors"][method] = anchor
            if anchor is None:
                row["eligibility_reasons"].append(
                    method + ": no prefix identity anchor"
                )
                continue
            identity = anchor["prediction_id"]
            if method == "A0":
                trace = json.loads(
                    (source / key / "A0/state-trace.json").read_text(encoding="utf-8")
                )
                state = next(
                    (s for s in trace[t - 1]["states"] if s["id"] == identity), None
                )
                if not state or not state["activated"]:
                    row["eligibility_reasons"].append(
                        "A0: no initialized retained state"
                    )
            else:
                log = json.loads(
                    (source / key / "B0/event-log.json").read_text(encoding="utf-8")
                )
                if identity not in log[t - 1]["active_ids"]:
                    row["eligibility_reasons"].append(
                        "B0: designated state already deleted"
                    )
                accepted = [
                    e["frame"]
                    for e in log[:t]
                    for a in e["actions"]
                    if a.get("id") == identity
                    and a["action"] in {"refresh", "discover"}
                ]
                if not accepted or t - max(accepted) > videos["sam_retention_steps"]:
                    row["eligibility_reasons"].append(
                        "B0: designated state expires before correction"
                    )
        observations = [
            o
            for o in cache[key]["YOLO"][t]
            if truth
            and o.category == truth.category
            and o.score >= videos["sam_prompt_conf"]
            and box_iou(o.box, truth.box) >= config["correction_box_min_iou"]
        ]
        detection = (
            max(observations, key=lambda o: (box_iou(o.box, truth.box), o.score))
            if observations
            else None
        )
        row["corrections"] = {
            "yolo": (
                {
                    "box": detection.box.tolist(),
                    "score": detection.score,
                    "detector_index": detection.identity,
                }
                if detection
                else None
            ),
            "reference": (
                {
                    "box": truth.box.tolist(),
                    "score": 1.0,
                    "detector_index": detection.identity if detection else None,
                }
                if truth
                else None
            ),
        }
        row["eligible_common_state"] = not row["eligibility_reasons"]
        row["condition_eligibility"] = {
            condition: row["eligible_common_state"]
            and row["corrections"][condition] is not None
            for condition in config["conditions"]
        }
        row["routing_policy"] = (
            "first prefix IoU-qualified identity; explicit diagnostic correction routing; fixed ID scored thereafter"
        )
        events.append(row)
    return events
