"""Study-level checks and 8/20/30-step reports from SAVED predictions only.

Read main() -> build() for the workflow. This does not load YOLO/SAM or start
a server. The normal run is the primary experiment; skip-one is a separate
mechanism diagnostic. A branches are unchanged negative controls in skip-one.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from .common import digest, load_predictions, mask_iou, write_json
from .recovery import assert_same_predictions
from .recovery_metrics import evaluate_recovery
from .recovery_report import verify_recovery, write_csv


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def key(record):
    return record["event"], record["condition"], record["group"]


def different_frames(first, second, identity=None):
    """Exact differences, not merely a changed aggregate score."""
    if len(first) != len(second):
        raise ValueError("Cannot compare different frame counts")
    changed = []
    for t, (a, b) in enumerate(zip(first, second)):
        if identity is not None:
            a, b = ([x for x in frame if x.identity == identity] for frame in (a, b))
        try:
            assert_same_predictions(a, b)
        except AssertionError:
            changed.append(t)
    return changed


def checkpoint_score(gt, predictions, trace, event, record, window, config):
    """Rescore one prefix of the SAME long prediction, not new inference."""
    stop = event["frame"] + window + 1
    return evaluate_recovery(
        gt[:stop],
        predictions[:stop],
        record["prediction_id"],
        event["gt_id"],
        event["frame"],
        window,
        config["mask_iou_threshold"],
        config["streak_required"],
        trace[:stop] if trace else None,
    )


def plot_refresh_comparison(path, normal, skipped, event, condition, threshold):
    """Four SAM curves, one fixed-ID target, identical correction source."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1200, 540), "white")
    draw, font = ImageDraw.Draw(image), ImageFont.load_default(size=17)
    draw.text(
        (25, 12),
        f'{event["name"]} / {condition} | SAM fixed ID | correction excluded',
        fill="black",
        font=font,
    )
    colors = {
        "normal B-H": "#147d46",
        "normal B-R": "#cf6500",
        "skip B-H": "#2078bd",
        "skip B-R": "#a331a3",
    }
    left, top, width, height = 65, 105, 1050, 330
    for value in (0, 0.5, 1):
        y = top + height * (1 - value)
        draw.line((left, y, left + width, y), fill="#dddddd")
        draw.text((15, y - 8), str(value), fill="black", font=font)
    for index, (label, color) in enumerate(colors.items()):
        draw.text((35 + index * 285, 55), label, fill=color, font=font)
        mode, group = label.split(" ")
        curve = (normal if mode == "normal" else skipped)[group]["curve"]
        previous = None
        for row in curve:
            if row["mask_iou"] is None:
                previous = None
                continue
            point = (
                left + (row["offset"] - 1) * width / (len(curve) - 1),
                top + height * (1 - row["mask_iou"]),
            )
            if previous:
                draw.line((*previous, *point), fill=color, width=3)
            previous = point
    for offset in [1, 5, 10, 15, 20, 25, 30]:
        draw.text(
            (left + (offset - 1) * width / 29 - 5, 450),
            str(offset),
            fill="black",
            font=font,
        )
    draw.text(
        (25, 490),
        f"Threshold {threshold}; exported steps, NOT seconds. Overlapping curves can hide one another.",
        fill="black",
        font=font,
    )
    image.save(path)


def build(normal_root, skipped_root, previous_root, output):
    normal_root, skipped_root, previous_root, output = map(
        Path, (normal_root, skipped_root, previous_root, output)
    )
    if output.exists():
        raise FileExistsError(
            "Choose a new study-report folder; never replace old reports"
        )
    normal, videos, gt, baseline_source, nv = verify_recovery(normal_root)
    skipped, _, _, _, sv = verify_recovery(skipped_root)
    previous = read_json(previous_root / "summary.json")
    assert previous["status"] == normal["status"] == skipped["status"] == "completed"
    assert normal["configuration"]["sam_skip_next_refresh"] is False
    assert skipped["configuration"]["sam_skip_next_refresh"] is True
    excluded = {"role", "sam_skip_next_refresh"}
    assert {k: v for k, v in normal["configuration"].items() if k not in excluded} == {
        k: v for k, v in skipped["configuration"].items() if k not in excluded
    }
    assert (
        normal["baseline_summary_sha256"]
        == skipped["baseline_summary_sha256"]
        == previous["baseline_summary_sha256"]
    )
    # Presentation modules can be added while a long GPU job is running.
    # All code that affects inference/routing/scoring must match, including
    # the read-only assignment probe; compare their frozen snapshots.
    inference_modules = (
        "recovery.py",
        "recovery_engines.py",
        "recovery_state.py",
        "recovery_events.py",
        "recovery_metrics.py",
        "association_trace.py",
        "sam_io.py",
        "sam_baseline.py",
        "bytetrack.py",
        "common.py",
    )
    for name in inference_modules:
        assert normal["source_sha256"][name] == skipped["source_sha256"][name], name
    config = normal["configuration"]
    assert config["report_windows"] == [8, 20, 30] and config["window"] == 30
    lookup = {
        mode: {key(r): r for r in summary["branches"]}
        for mode, summary in [
            ("normal", normal),
            ("skip", skipped),
            ("previous", previous),
        ]
    }
    assert lookup["normal"].keys() == lookup["skip"].keys() == lookup["previous"].keys()
    checks, scores, pair_rows, prompts, assignment_rows, curves = [], [], [], [], [], []
    all_results = {"normal": {}, "skip": {}}
    # First verify compatibility and treatment fidelity BEFORE writing findings.
    for k, record in lookup["normal"].items():
        event = next(e for e in normal["events"] if e["name"] == record["event"])
        old = load_predictions(previous_root / lookup["previous"][k]["folder"])
        main = load_predictions(normal_root / record["folder"])
        skip_record = lookup["skip"][k]
        for field in ("prediction_id", "prefix_target_sha256", "correction"):
            assert record[field] == skip_record[field] == lookup["previous"][k][field]
        alternative = load_predictions(skipped_root / skip_record["folder"])
        assert not different_frames(
            old, main[: len(old)]
        ), f"Old 8-step result changed: {k}"
        changed = different_frames(main, alternative)
        if record["group"].startswith("A"):
            assert not changed, f"SAM treatment unexpectedly changed A: {k}"
        else:
            slot = skip_record["skipped_refresh_step"]
            assert all(t >= slot for t in changed), f"Changed before treatment: {k}"
        checks.append(
            {
                "event": k[0],
                "condition": k[1],
                "group": k[2],
                "old_8_steps_exact": True,
                "normal_vs_skip_changed_frames": changed,
                "designated_target_changed_frames": different_frames(
                    main, alternative, record["prediction_id"]
                ),
            }
        )
        for mode, root, branch_record in [
            ("normal", normal_root, record),
            ("skip", skipped_root, skip_record),
        ]:
            folder = root / branch_record["folder"]
            prediction = main if mode == "normal" else alternative
            trace = read_json(folder / "state-trace.json")
            all_results[mode][k] = read_json(folder / "recovery.json")
            for window in config["report_windows"]:
                result = checkpoint_score(
                    gt[event["video_id"]],
                    prediction,
                    trace,
                    event,
                    branch_record,
                    window,
                    config,
                )
                scores.append(
                    {
                        "mode": mode,
                        "event": k[0],
                        "condition": k[1],
                        "group": k[2],
                        "window": window,
                        **result["summary"],
                        "final_correct_streak": result["curve"][-1]["success_streak"],
                    }
                )
            for row in trace[event["frame"] :]:
                truth = next(
                    (
                        x
                        for x in gt[event["video_id"]][row["frame"]]
                        if x.identity == event["gt_id"]
                    ),
                    None,
                )
                actions = row.get("actions", [])
                if k[2].startswith("B"):
                    prompts.append(
                        {
                            "mode": mode,
                            "event": k[0],
                            "condition": k[1],
                            "group": k[2],
                            "frame": row["frame"],
                            "offset": row["frame"] - event["frame"],
                            "target_active": record["prediction_id"]
                            in row["active_ids"],
                            "target_output": record["prediction_id"]
                            in row["output_ids"],
                            "target_actions": ";".join(
                                a["action"]
                                for a in actions
                                if a.get("id") == record["prediction_id"]
                            ),
                        }
                    )
                if k[2].startswith("A") and mode == "normal":
                    for category in row["assignments"]:
                        if category["category"] != event["category"]:
                            continue
                        for stage in category["stages"]:
                            for ri, track in enumerate(stage["tracks"]):
                                if track["external_id"] != record["prediction_id"]:
                                    continue
                                matched = {
                                    int(a): int(b) for a, b in stage["matches"]
                                }.get(ri)
                                for di, det in enumerate(stage["detections"]):
                                    cost = stage["assignment_cost"][ri][di]
                                    assignment_rows.append(
                                        {
                                            "event": k[0],
                                            "condition": k[1],
                                            "group": k[2],
                                            "frame": row["frame"],
                                            "stage": stage["stage"],
                                            "fixed_id": record["prediction_id"],
                                            "detector_index": det["detector_index"],
                                            "detector_score": det["score"],
                                            "raw_iou_cost": stage["raw_iou_cost"][ri][
                                                di
                                            ],
                                            "assignment_cost": cost,
                                            "threshold": stage["threshold"],
                                            "within_threshold": cost
                                            <= stage["threshold"],
                                            "chosen": matched == di,
                                            "predicted_box": json.dumps(
                                                track["predicted_box"]
                                            ),
                                            "detection_box": json.dumps(det["box"]),
                                        }
                                    )
            curves += [
                {"mode": mode, "event": k[0], "condition": k[1], "group": k[2], **r}
                for r in all_results[mode][k]["curve"]
            ]
    # Check the scheduled skip actually removed exactly what normal would use.
    treatment_checks = []
    for k, record in lookup["skip"].items():
        if not k[2].startswith("B"):
            continue
        slot, identity = record["skipped_refresh_step"], record["prediction_id"]
        a, b = [
            read_json(root / lookup[mode][k]["folder"] / "state-trace.json")[slot]
            for mode, root in [("normal", normal_root), ("skip", skipped_root)]
        ]
        normal_refresh = any(
            x["action"] == "refresh" and x.get("id") == identity for x in a["actions"]
        )
        removed = [
            x
            for x in b["actions"]
            if x["action"] == "skipped_refresh" and x.get("id") == identity
        ]
        assert bool(removed) == normal_refresh
        treatment_checks.append(
            {
                "event": k[0],
                "condition": k[1],
                "group": k[2],
                "scheduled_step": slot,
                "normal_had_refresh": normal_refresh,
                "actual_refresh_removed": bool(removed),
            }
        )
    for mode in ("normal", "skip"):
        for event in normal["events"]:
            for condition in config["conditions"]:
                for window in config["report_windows"]:
                    for letter in ("A", "B"):
                        h, r = [
                            next(
                                row
                                for row in scores
                                if row["mode"] == mode
                                and row["event"] == event["name"]
                                and row["condition"] == condition
                                and row["window"] == window
                                and row["group"] == letter + suffix
                            )
                            for suffix in ("-H", "-R")
                        ]
                        native = load_predictions(
                            baseline_source
                            / str(event["video_id"])
                            / ("A0" if letter == "A" else "B0")
                        )
                        native_record = lookup[mode][
                            event["name"], condition, letter + "-H"
                        ]
                        reference = checkpoint_score(
                            gt[event["video_id"]],
                            native,
                            None,
                            event,
                            native_record,
                            window,
                            config,
                        )["summary"]
                        pair_rows.append(
                            {
                                "mode": mode,
                                "event": event["name"],
                                "condition": condition,
                                "model": letter,
                                "window": window,
                                "native_mean_iou": reference["mean_visible_mask_iou"],
                                "H_mean_iou": h["mean_visible_mask_iou"],
                                "R_mean_iou": r["mean_visible_mask_iou"],
                                "R_minus_H_mean_iou": r["mean_visible_mask_iou"]
                                - h["mean_visible_mask_iou"],
                                "H_correct": h["correct_visible_steps"],
                                "R_correct": r["correct_visible_steps"],
                                "visible": h["visible_steps"],
                                "H_confirmed": h["recovery_confirmed_offset"],
                                "R_confirmed": r["recovery_confirmed_offset"],
                                "H_longest": h["longest_correct_streak"],
                                "R_longest": r["longest_correct_streak"],
                                "H_relapses": h["relapses"],
                                "R_relapses": r["relapses"],
                            }
                        )
    output.mkdir(parents=True)
    write_csv(output / "checkpoint-scores.csv", scores)
    write_csv(output / "checkpoint-pairs.csv", pair_rows)
    write_csv(output / "prompt-timeline.csv", prompts)
    write_csv(output / "assignment-candidates.csv", assignment_rows)
    write_csv(output / "frame-curves.csv", curves)
    for event in normal["events"]:
        for condition in config["conditions"]:
            plot_refresh_comparison(
                output / f'{event["name"]}-{condition}-refresh-curves.png',
                {
                    g: all_results["normal"][event["name"], condition, g]
                    for g in ("B-H", "B-R")
                },
                {
                    g: all_results["skip"][event["name"], condition, g]
                    for g in ("B-H", "B-R")
                },
                event,
                condition,
                config["mask_iou_threshold"],
            )
    verification = {
        "status": "passed",
        "normal_run": str(normal_root.resolve()),
        "skip_run": str(skipped_root.resolve()),
        "previous_run": str(previous_root.resolve()),
        "normal_verification": nv,
        "skip_verification": sv,
        "run_summary_sha256": {
            str(root.resolve()): digest(root / "summary.json")
            for root in (normal_root, skipped_root, previous_root)
        },
        "compatibility_checks": checks,
        "treatment_checks": treatment_checks,
        "limitations": [
            "Two development events, not population-level evidence.",
            "Fixed designated ID; no best-track reselection.",
            "Skip is one target's next scheduled refresh, not first future successful match; lifecycle rules unchanged.",
            "Gray/native reference retains the NORMAL schedule, including in skip diagnostic reports.",
            "Threshold .5/streak 3/checkpoints 8,20,30 frozen for this development batch, not final protocol.",
        ],
    }
    write_json(output / "study-verification.json", verification)
    print(
        json.dumps(
            {
                "status": "passed",
                "output": str(output),
                "checkpoint_rows": len(scores),
                "treatment_checks": treatment_checks,
            },
            indent=2,
        )
    )
    return verification


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("normal", "skip", "previous", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    build(args.normal, args.skip, args.previous, args.output)


if __name__ == "__main__":
    main()
