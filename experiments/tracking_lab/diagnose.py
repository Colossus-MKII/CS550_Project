"""Offline, class-aware frame diagnostics, distinct from global tracking metrics.

Best-mask IoU is localization-only and IGNORES identity; missing visible GT gets
zero. Frame matches are gated one-to-one and never supplied back to inference.
ID changes here are visual-review flags, not a replacement for TrackEval IDSW.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment

from .common import box_iou, mask_iou


def diagnose(gt, predictions, detections):
    if not len(gt) == len(predictions) == len(detections):
        raise ValueError("Frame counts differ")
    frames = []
    previous = {}
    for t, (g, p, d) in enumerate(zip(gt, predictions, detections)):
        similarity = np.array(
            [
                [mask_iou(a.mask, b.mask) if a.category == b.category else 0 for b in p]
                for a in g
            ]
        ).reshape(len(g), len(p))
        valid = similarity >= 0.5
        pairs = []
        if len(g) and len(p):
            rows, cols = linear_sum_assignment(
                -(valid * (min(len(g), len(p)) + 1 + similarity))
            )
            pairs = [(int(r), int(c)) for r, c in zip(rows, cols) if valid[r, c]]
        matches = dict(pairs)
        used = {j for _, j in pairs}
        targets = []
        changes = 0
        for i, obj in enumerate(g):
            same = [o for o in d if o.category == obj.category]
            det_box = max((box_iou(obj.box, o.box) for o in same), default=0.0)
            det_mask = max((mask_iou(obj.mask, o.mask) for o in same), default=0.0)
            best = float(similarity[i].max()) if p else 0.0
            match = p[matches[i]] if i in matches else None
            identity_changed = bool(
                match
                and obj.identity in previous
                and previous[obj.identity] != match.identity
            )
            if match:
                previous[obj.identity] = match.identity
            changes += identity_changed
            if match:
                reason = "matched_id_changed" if identity_changed else "matched"
            elif det_mask >= 0.5:
                reason = "good_yolo_mask_but_no_matching_output"
            elif det_box >= 0.5:
                reason = "yolo_box_ok_mask_or_propagation_poor"
            else:
                reason = "no_adequate_same_class_yolo_box"
            targets.append(
                {
                    "gt_id": obj.identity,
                    "category": obj.category,
                    "best_mask_iou": best,
                    "matched_prediction_id": match.identity if match else None,
                    "matched_iou": float(similarity[i, matches[i]]) if match else 0.0,
                    "diagnostic_id_change": identity_changed,
                    "yolo_box_iou": det_box,
                    "yolo_mask_iou": det_mask,
                    "reason": reason,
                }
            )
        frames.append(
            {
                "frame": t,
                "targets": targets,
                "TP": len(pairs),
                "FN": len(g) - len(pairs),
                "FP": len(p) - len(used),
                "unmatched_prediction_ids": [
                    o.identity for j, o in enumerate(p) if j not in used
                ],
                "diagnostic_id_changes": changes,
                "mean_best_mask_iou": (
                    float(np.mean([o["best_mask_iou"] for o in targets]))
                    if targets
                    else None
                ),
            }
        )
    values = [
        target["best_mask_iou"] for frame in frames for target in frame["targets"]
    ]
    summary = {
        "mean_best_same_class_mask_iou_visible_gt": (
            float(np.mean(values)) if values else None
        ),
        "frame_diagnostic_FP": sum(f["FP"] for f in frames),
        "frame_diagnostic_FN": sum(f["FN"] for f in frames),
        "diagnostic_id_changes": sum(f["diagnostic_id_changes"] for f in frames),
        "note": "Frame matching/best-IoU diagnostics ignore global ID assignment; official metrics are reported separately.",
    }
    return frames, summary
