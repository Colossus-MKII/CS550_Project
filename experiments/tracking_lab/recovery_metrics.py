"""Fixed-target, AFTER-correction recovery scoring. No best-track reselection."""

from .common import box_iou, mask_iou


def evaluate_recovery(
    gt,
    predictions,
    identity,
    gt_identity,
    correction,
    window,
    threshold=0.5,
    streak_required=3,
    trace=None,
):
    if len(gt) != len(predictions):
        raise ValueError("Prediction/GT length mismatch")
    if not 0 < threshold <= 1 or streak_required < 1 or window < streak_required:
        raise ValueError("Invalid recovery rule")
    stop = correction + window
    if stop >= len(gt):
        raise ValueError("Insufficient post-correction window")
    rows = []
    streak = longest = relapses = 0
    first_start = confirmed = None
    had_recovery = False
    currently_recovered = False
    for t in range(correction + 1, stop + 1):
        truth = next((o for o in gt[t] if o.identity == gt_identity), None)
        found = [o for o in predictions[t] if o.identity == identity]
        if len(found) > 1:
            raise ValueError("Duplicate designated prediction ID")
        pred = found[0] if found else None
        visible = truth is not None
        iou = (
            mask_iou(truth.mask, pred.mask)
            if visible and pred and pred.category == truth.category
            else 0.0
        )
        correct = visible and iou >= threshold
        streak = streak + 1 if correct else 0  # Invisible breaks the streak too.
        longest = max(longest, streak)
        if streak >= streak_required:
            if confirmed is None:
                confirmed, first_start = t, t - streak_required + 1
            had_recovery = currently_recovered = True
        elif visible and not correct and currently_recovered:
            relapses += 1
            currently_recovered = False
        row = {
            "frame": t,
            "offset": t - correction,
            "visible": visible,
            "output_present": pred is not None,
            "mask_iou": iou if visible else None,
            "correct": bool(correct),
            "success_streak": streak,
            "wrong_output_when_invisible": bool(not visible and pred is not None),
        }
        if trace:
            target = next(
                (s for s in trace[t].get("states", []) if s["id"] == identity), None
            )
            if target and visible:
                row["state_box_iou"] = box_iou(target["box_xyxy"], truth.box)
                if target.get("predicted_box") is not None:
                    row["motion_prediction_box_iou"] = box_iou(
                        target["predicted_box"], truth.box
                    )
        rows.append(row)
    visible_rows = [row for row in rows if row["visible"]]
    return {
        "summary": {
            "recovered": had_recovery,
            "visible_steps": len(visible_rows),
            "correct_visible_steps": sum(row["correct"] for row in visible_rows),
            "correct_visible_fraction": (
                sum(row["correct"] for row in visible_rows) / len(visible_rows)
                if visible_rows
                else None
            ),
            "mean_visible_mask_iou": (
                sum(row["mask_iou"] for row in visible_rows) / len(visible_rows)
                if visible_rows
                else None
            ),
            "recovery_onset_offset": (
                first_start - correction if first_start is not None else None
            ),
            "recovery_confirmed_offset": (
                confirmed - correction if confirmed is not None else None
            ),
            "longest_correct_streak": longest,
            "relapses": relapses,
            "invisible_false_outputs": sum(
                row["wrong_output_when_invisible"] for row in rows
            ),
        },
        "curve": rows,
        "rule": {
            "mask_iou_threshold": threshold,
            "required_consecutive_exported_steps": streak_required,
            "window_exported_steps": window,
            "correction_frame_excluded": True,
            "identity": identity,
            "gt_identity": gt_identity,
            "invisible_policy": "break_streak; score false outputs separately",
        },
    }
