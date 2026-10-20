"""Verify and render SAVED recovery results. No GPU model and no web server.

Produces scores.csv, paired-differences.csv, frame-curves.csv, PNG curves,
six-panel MP4s and a text reading guide in the existing experiment run folder.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import digest, load_predictions, write_json, mask_iou
from .dataset import read_manifest, load_ground_truth
from .recovery_metrics import evaluate_recovery
from .recovery import assert_same_predictions
from .runtime import resolve_data_root


def write_csv(path, rows):
    if not rows:
        raise ValueError("No rows to report")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def mean_curve_field(result, field):
    values = [row[field] for row in result["curve"] if row.get(field) is not None]
    return sum(values) / len(values) if values else None


def source_detection_indices(prediction, detections):
    """Read-only A-output provenance; do not infer a match from GT overlap.

    ByteTrack outputs carry the original YOLO mask, box and score. Exact equality
    reconstructs which cached observations supplied that output. Keep all equal
    candidates rather than pretending identical detector rows are unambiguous.
    This does not record the tracker's internal assignment costs.
    """
    return [
        item.identity
        for item in detections
        if item.category == prediction.category
        and item.score == prediction.score
        and np.array_equal(item.box, prediction.box)
        and np.array_equal(item.mask, prediction.mask)
    ]


def verify_recovery(output, data_root=None):
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] not in {"inference_completed", "completed"}:
        raise ValueError("Do not report an incomplete/failed run")
    root = resolve_data_root(output, summary, data_root)
    for name, fingerprint in summary["source_sha256"].items():
        assert digest(output / "code" / (name + ".txt")) == fingerprint
    source = Path(summary["baseline_source"])
    assert digest(source / "summary.json") == summary["baseline_summary_sha256"]
    for name, expected_hash in summary.get("baseline_files_sha256", {}).items():
        assert digest(source / name) == expected_hash, name
    ids = list(dict.fromkeys(e["video_id"] for e in summary["events"]))
    videos, records, _ = read_manifest(root, ids)
    ground_truth = {
        v.video_id: load_ground_truth(root, r) for v, r in zip(videos, records)
    }
    config = summary["configuration"]
    expected = {
        (e["name"], condition, group)
        for e in summary["events"]
        for condition, eligible in e["condition_eligibility"].items()
        if eligible
        for group in ("A-H", "A-R", "B-H", "B-R")
    }
    actual = [(r["event"], r["condition"], r["group"]) for r in summary["branches"]]
    assert len(actual) == len(set(actual)) and set(actual) == expected
    for record in summary["branches"]:
        event = next(e for e in summary["events"] if e["name"] == record["event"])
        folder = output / record["folder"]
        prediction = load_predictions(folder)
        trace = json.loads((folder / "state-trace.json").read_text())
        t = event["frame"]
        assert len(prediction) == t + config["window"] + 1 == len(trace)
        baseline = (
            load_predictions(source / str(event["video_id"]) / "A0")
            if record["group"].startswith("A")
            else load_predictions(
                output / "baseline_replay" / str(event["video_id"]) / "B0"
            )
        )
        for frame in range(t):
            assert_same_predictions(baseline[frame], prediction[frame])
        intervention = trace[t]["intervention"]
        assert intervention["correction_updates"] == 1
        assert intervention["external_id"] == record["prediction_id"]
        assert intervention["reset"] == record["group"].endswith("R")
        assert all(row["intervention"] is None for row in trace[t + 1 :])
        if record["group"].startswith("B"):
            slots = [
                (row["frame"], action["id"])
                for row in trace
                for action in row.get("actions", [])
                if action["action"] == "skip_refresh_slot"
            ]
            expected_skip = record.get("skipped_refresh_step")
            assert slots == (
                []
                if expected_skip is None
                else [(expected_skip, record["prediction_id"])]
            )
            skipped = [
                (row["frame"], action["id"])
                for row in trace
                for action in row.get("actions", [])
                if action["action"] == "skipped_refresh"
            ]
            assert all(item in slots for item in skipped) and len(skipped) <= 1
            if expected_skip is not None:
                assert not any(
                    action["action"] == "refresh"
                    and action["id"] == record["prediction_id"]
                    for action in trace[expected_skip].get("actions", [])
                )
        if record["group"] == "B-R":
            cleared = intervention["clear"]["after_clear"]
            assert all(
                not cleared[key]
                for key in (
                    "point_frames",
                    "mask_frames",
                    "conditioning_frames",
                    "nonconditioning_frames",
                    "tracked_frames",
                )
            )
            assert intervention["clear"]["other_targets_unchanged"]
            assert intervention["after"]["point_frames"] == [t]
            assert intervention["after"]["conditioning_frames"] == [t]
        if record["group"] == "B-H":
            assert set(intervention["before"]["conditioning_frames"]) <= set(
                intervention["after"]["conditioning_frames"]
            )
        if record["group"].startswith("A"):
            from ultralytics.trackers.utils.kalman_filter import KalmanFilterXYAH

            box = np.asarray(record["correction"]["box"], np.float32)
            xyah = np.array(
                [
                    (box[0] + box[2]) / 2,
                    (box[1] + box[3]) / 2,
                    (box[2] - box[0]) / (box[3] - box[1]),
                    box[3] - box[1],
                ]
            )
            kf = KalmanFilterXYAH()
            if record["group"] == "A-R":
                mean, cov = kf.initiate(xyah)
                assert mean[4:].tolist() == [0, 0, 0, 0]
            else:
                before = intervention["before"]
                mean, cov = np.array(before["mean"]), np.array(before["covariance"])
                if before["state"] != 1:
                    mean[7] = 0
                mean, cov = kf.predict(mean, cov)
                mean, cov = kf.update(mean, cov, xyah)
            np.testing.assert_allclose(
                intervention["after"]["mean"], mean, rtol=0, atol=1e-12
            )
            np.testing.assert_allclose(
                intervention["after"]["covariance"], cov, rtol=0, atol=1e-12
            )
        gt = ground_truth[event["video_id"]][: len(prediction)]
        recalculated = evaluate_recovery(
            gt,
            prediction,
            record["prediction_id"],
            event["gt_id"],
            t,
            config["window"],
            config["mask_iou_threshold"],
            config["streak_required"],
            trace,
        )
        assert recalculated == json.loads((folder / "recovery.json").read_text())
    # H/R metadata and prefixes must agree WITHIN each model and condition.
    for event, condition, _ in expected:
        for letter in ("A", "B"):
            pair = [
                r
                for r in summary["branches"]
                if r["event"] == event
                and r["condition"] == condition
                and r["group"].startswith(letter)
            ]
            assert len(pair) == 2
            for key in ("prediction_id", "prefix_target_sha256", "correction"):
                assert pair[0][key] == pair[1][key]
    return (
        summary,
        videos,
        ground_truth,
        source,
        {
            "status": "passed",
            "branches": len(actual),
            "prefixes": "exact against synchronized native B0 and historical A0",
            "independent_rescoring": True,
            "one_correction_per_branch": True,
            "fixed_ids": True,
            "reset_audits": True,
        },
    )


def plot_curves(path, scores, baseline, title, threshold):
    image = Image.new("RGB", (1100, 470), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=17)
    draw.text(
        (30, 12),
        title + " | fixed designated ID | post-correction steps",
        fill="black",
        font=font,
    )
    colors = {"H": "#148050", "R": "#cb6300", "baseline": "#777777"}
    for panel, letter in enumerate(("A", "B")):
        left, top, width, height = 60 + panel * 545, 75, 440, 270
        draw.text(
            (left, top - 30),
            letter + ": H=retain / R=reset / gray=no correction",
            fill="black",
            font=font,
        )
        for value in (0, 0.5, 1):
            y = top + height * (1 - value)
            draw.line((left, y, left + width, y), fill="#dddddd")
            draw.text((left - 38, y - 8), str(value), fill="black", font=font)
        draw.rectangle((left, top, left + width, top + height), outline="black")
        n = len(scores[letter + "-H"]["curve"])
        draw.line(
            (
                left,
                top + height * (1 - threshold),
                left + width,
                top + height * (1 - threshold),
            ),
            fill="#aaaaaa",
            width=2,
        )
        for name, result in [
            ("baseline", baseline[letter]),
            ("H", scores[letter + "-H"]),
            ("R", scores[letter + "-R"]),
        ]:
            previous = None
            for row in result["curve"]:
                x = left + (row["offset"] - 1) * width / max(1, n - 1)
                y = (
                    top + height * (1 - row["mask_iou"])
                    if row["mask_iou"] is not None
                    else None
                )
                if y is None:
                    previous = None
                    continue
                if previous:
                    draw.line((*previous, x, y), fill=colors[name], width=3)
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=colors[name])
                previous = x, y
        ticks = range(1, n + 1) if n <= 10 else [1] + list(range(5, n + 1, 5))
        for offset in ticks:
            draw.text(
                (left + (offset - 1) * width / max(1, n - 1) - 4, top + height + 9),
                str(offset),
                fill="black",
                font=font,
            )
    draw.text(
        (35, 400),
        "Mask IoU; invisible steps are gaps. Corrected frame excluded. Threshold line is provisional.",
        fill="black",
        font=font,
    )
    draw.text(
        (35, 430),
        "Short development pilot, not a final ranking or a causal comparison between memory types.",
        fill="black",
        font=font,
    )
    image.save(path)


def build(output, data_root=None):
    import cv2
    from .render import VideoWriter, label, overlay

    output = Path(output).resolve()
    summary, videos, gt, source, verification = verify_recovery(output, data_root)
    config = summary["configuration"]
    artifacts = output / "visuals"
    artifacts.mkdir(exist_ok=True)
    all_curves, paired, associations = [], [], []
    for event in summary["events"]:
        if not event["eligible_common_state"]:
            continue
        video = next(v for v in videos if v.video_id == event["video_id"])
        t, stop = event["frame"], event["frame"] + config["window"] + 1
        for condition in config["conditions"]:
            if not event["condition_eligibility"][condition]:
                continue
            records = {
                r["group"]: r
                for r in summary["branches"]
                if r["event"] == event["name"] and r["condition"] == condition
            }
            predictions = {
                group: load_predictions(output / r["folder"])
                for group, r in records.items()
            }
            scores = {
                group: json.loads((output / r["folder"] / "recovery.json").read_text())
                for group, r in records.items()
            }
            native = {
                "A": load_predictions(source / str(video.video_id) / "A0")[:stop],
                "B": load_predictions(
                    output / "baseline_replay" / str(video.video_id) / "B0"
                )[:stop],
            }
            baseline = {
                letter: evaluate_recovery(
                    gt[video.video_id][:stop],
                    frames,
                    records[letter + "-H"]["prediction_id"],
                    event["gt_id"],
                    t,
                    config["window"],
                    config["mask_iou_threshold"],
                    config["streak_required"],
                )
                for letter, frames in native.items()
            }
            detector_cache = load_predictions(source / str(video.video_id) / "YOLO")
            for group in ("A-H", "A-R"):
                for frame in range(t + 1, stop):
                    truth = next(
                        (
                            x
                            for x in gt[video.video_id][frame]
                            if x.identity == event["gt_id"]
                        ),
                        None,
                    )
                    associations.append(
                        {
                            "event": event["name"],
                            "condition": condition,
                            "group": group,
                            "frame": frame,
                            "designated_id": records[group]["prediction_id"],
                            "outputs": [
                                {
                                    "id": item.identity,
                                    "source_detection_indices": source_detection_indices(
                                        item, detector_cache[frame]
                                    ),
                                    "target_mask_iou": (
                                        mask_iou(truth.mask, item.mask)
                                        if truth
                                        else None
                                    ),
                                }
                                for item in predictions[group][frame]
                                if item.category == event["category"]
                            ],
                        }
                    )
            write_json(
                artifacts / f'{event["name"]}-{condition}-baseline.json', baseline
            )
            plot_curves(
                artifacts / f'{event["name"]}-{condition}-curves.png',
                scores,
                baseline,
                event["name"] + " / " + condition,
                config["mask_iou_threshold"],
            )
            for group, result in scores.items():
                all_curves += [
                    {
                        "event": event["name"],
                        "condition": condition,
                        "group": group,
                        **row,
                    }
                    for row in result["curve"]
                ]
            for letter in ("A", "B"):
                h, r = (scores[letter + suffix]["summary"] for suffix in ("-H", "-R"))
                paired.append(
                    {
                        "event": event["name"],
                        "condition": condition,
                        "model": letter,
                        "uncorrected_mean_iou": baseline[letter]["summary"][
                            "mean_visible_mask_iou"
                        ],
                        "H_mean_iou": h["mean_visible_mask_iou"],
                        "R_mean_iou": r["mean_visible_mask_iou"],
                        "R_minus_H_mean_iou": (
                            r["mean_visible_mask_iou"] - h["mean_visible_mask_iou"]
                            if h["mean_visible_mask_iou"] is not None
                            else None
                        ),
                        "H_recovered": h["recovered"],
                        "R_recovered": r["recovered"],
                        "uncorrected_correct_fraction": baseline[letter]["summary"][
                            "correct_visible_fraction"
                        ],
                        "H_correct_fraction": h["correct_visible_fraction"],
                        "R_correct_fraction": r["correct_visible_fraction"],
                        "H_relapses": h["relapses"],
                        "R_relapses": r["relapses"],
                        "H_confirmed_offset": h["recovery_confirmed_offset"],
                        "R_confirmed_offset": r["recovery_confirmed_offset"],
                        "H_motion_prediction_box_iou": mean_curve_field(
                            scores[letter + "-H"], "motion_prediction_box_iou"
                        ),
                        "R_motion_prediction_box_iou": mean_curve_field(
                            scores[letter + "-R"], "motion_prediction_box_iou"
                        ),
                    }
                )
            movie = artifacts / f'{event["name"]}-{condition}-four-groups.mp4'
            writer = VideoWriter(movie, (video.width * 2, (video.height + 32) * 3), 5)
            try:
                for frame in range(max(0, t - 2), stop):
                    rgb = cv2.imread(str(video.rgb_paths[frame]))
                    truth = [
                        x
                        for x in gt[video.video_id][frame]
                        if x.identity == event["gt_id"]
                    ]
                    panel = [
                        label(
                            rgb,
                            f'RGB | step {frame} | {"CORRECTION EXCLUDED" if frame==t else "offset "+str(frame-t)}',
                        ),
                        label(
                            overlay(rgb, truth),
                            f'GT target {event["gt_id"]} | {condition} box',
                        ),
                    ]
                    for group in ("A-H", "A-R", "B-H", "B-R"):
                        designated = [
                            x
                            for x in predictions[group][frame]
                            if x.identity == records[group]["prediction_id"]
                        ]
                        iou = (
                            mask_iou(truth[0].mask, designated[0].mask)
                            if truth and designated
                            else 0
                        )
                        quality_label = f"{iou:.3f}" if truth else "N/A (GT invisible)"
                        view = overlay(rgb, designated)
                        if frame == t:
                            x, y, x2, y2 = map(int, records[group]["correction"]["box"])
                            cv2.rectangle(view, (x, y), (x2, y2), (255, 255, 0), 2)
                        panel.append(
                            label(
                                view,
                                f'{group} | fixed ID {records[group]["prediction_id"]} | mask IoU {quality_label}',
                            )
                        )
                    image = np.vstack(
                        [np.hstack(panel[row : row + 2]) for row in (0, 2, 4)]
                    )
                    writer.write(image)
                    if frame in {t + 1, t + 3, t + config["window"]}:
                        cv2.imwrite(
                            str(
                                artifacts
                                / f'{event["name"]}-{condition}-step{frame}.png'
                            ),
                            image,
                        )
            finally:
                writer.close()
            cap = cv2.VideoCapture(str(movie))
            assert cap.isOpened() and int(
                cap.get(cv2.CAP_PROP_FRAME_COUNT)
            ) == stop - max(0, t - 2)
            ok, _ = cap.read()
            cap.release()
            assert ok
    rows = [
        {key: value for key, value in row.items() if key not in {"correction"}}
        for row in summary["branches"]
    ]
    write_csv(output / "scores.csv", rows)
    write_csv(output / "paired-differences.csv", paired)
    write_csv(output / "frame-curves.csv", all_curves)
    write_json(
        output / "association-audit.json",
        {
            "policy": "Read-only exact YOLO mask/box/score provenance; not internal assignment-cost logging. GT overlaps are diagnostic only.",
            "frames": associations,
        },
    )
    lines = [
        "LOCAL FOUR-GROUP RECOVERY PILOT",
        "",
        f'{sum(e["eligible_common_state"] for e in summary["events"])} eligible events; {len(summary["branches"])} branches; {sum(not e["eligible_common_state"] for e in summary["events"])} ineligible candidates retained in events.json.',
        "Read paired-differences.csv first; then visuals/*-curves.png and *-four-groups.mp4.",
        "H=retain; R=reset. Compare H/R WITHIN A and WITHIN B. No pooled memory ranking.",
        "A = ByteTrack state; B = SAM target history. Weights frozen; fixed target IDs.",
        f'Only one box correction; exclude its frame; {config["window"]} following exported steps; IoU>={config["mask_iou_threshold"]} for {config["streak_required"]} consecutive visible steps.',
        "These are provisional development settings, not the final protocol. 5 fps is video BROWSING speed.",
        "A's correction frame has no designated mask output: state-only correction, no fabricated GT mask.",
        "Important: historical B0 prompt-frame displays were not reproducible with upstream asynchronous CPU offload.",
        "This run uses a CUDA synchronization guard before CPU consolidation and independent native B0 references.",
        "Old baseline and website outputs were NOT overwritten. See synchronized_reference in summary.json.",
        "",
        "PAIR RESULTS (R minus H mean visible mask IoU)",
    ]

    def display(value):
        return f"{value:.4f}" if value is not None else "NA"

    for row in paired:
        lines.append(
            f'{row["event"]:18s} {row["condition"]:10s} {row["model"]}  H={display(row["H_mean_iou"])} R={display(row["R_mean_iou"])} delta={display(row["R_minus_H_mean_iou"])}  recovered H/R={row["H_recovered"]}/{row["R_recovered"]}'
        )
    (output / "READ_RESULTS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    verification.update(
        {
            "videos_rendered": len(paired) // 2,
            "report_source_sha256": digest(Path(__file__)),
        }
    )
    write_json(output / "verification.json", verification)
    summary["status"] = "completed"
    write_json(output / "summary.json", summary)
    print(json.dumps(verification, indent=2))
    return verification


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--data-root", type=Path)
    args = p.parse_args(argv)
    build(args.output, args.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
