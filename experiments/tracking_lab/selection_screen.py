"""Development-only candidate queue, lossless export and RGB/GT review aids.

This module never imports a model, runs H/R, opens a server or touches an old
export. Trajectory/area hints rank cases for human inspection; they do not prove
occlusion or motion mechanisms. Camera translation is an approximate diagnostic.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import CLASSES, box_iou, digest, write_json
from .dataset import load_ground_truth, read_manifest
from .selection_split import OLD_VIDEOS, audit_records


def early_gap(record):
    n = record["features"]["video"]["shape"][0]
    return any(
        b > a + 1 and 10 <= b <= n - 31
        for track in record["tracks"]
        if track["category"] in CLASSES
        for a, b in zip(track["visible_frames"], track["visible_frames"][1:])
    )


def choose_candidates(split_path, audit_path, output, limit=32):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Candidate queue is frozen; choose a new version")
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    _, records = audit_records(audit_path)
    if split["audit_sha256"] != digest(audit_path):
        raise ValueError("Split/audit mismatch")
    indexed = {r["video_id"]: r for r in records}
    old_groups = {
        r["group_id"]
        for r in split["splits"]["development"]
        if r["video_id"] in OLD_VIDEOS
    }
    pool = [
        r
        for r in split["splits"]["development"]
        if r["video_id"] not in OLD_VIDEOS
        and r["frames"] >= 41
        and r["group_id"] not in old_groups
    ]
    rng = random.Random(550)
    rng.shuffle(pool)
    # One representative per visual duplicate group, before looking at models.
    representatives = {}
    for row in pool:
        representatives.setdefault(row["group_id"], row)
    pool = list(representatives.values())
    chosen = []

    def add(row):
        if row not in chosen and len(chosen) < limit:
            chosen.append(row)

    for row in pool:
        if early_gap(indexed[row["video_id"]]):
            add(row)
    for category in ("cat", "dog", "car", "person"):
        for row in [r for r in pool if category in r["categories"]][:2]:
            add(row)
    for row in pool:
        add(row)
    target_counts = Counter(c for r in records for c in r["target_categories"])

    def describe(row):
        record = indexed[row["video_id"]]
        return {
            **row,
            "focus": min(row["categories"], key=lambda c: (target_counts[c], c)),
            "early_visibility_gap_hint": early_gap(record),
            "target_tracks": sum(t["category"] in CLASSES for t in record["tracks"]),
        }

    result = {
        "schema": 1,
        "version": output.stem,
        "status": "frozen_before_candidate_baseline_inference",
        "split_sha256": digest(split_path),
        "seed": 550,
        "selection_information": "Development split, length, sparse visual group, audited categories and visibility gaps only; no H/R or model-quality ranking.",
        "video_ids": [r["video_id"] for r in chosen],
        "candidates": [describe(r) for r in chosen],
        "reserves": [describe(r) for r in pool if r not in chosen],
        "constraints": {
            "new_videos_only": True,
            "one_per_visual_group": True,
            "minimum_prefix": 10,
            "followup": 30,
        },
        "H_R_permitted": False,
        "excluded_old_visual_groups": sorted(old_groups),
        "validation_evaluation_access": "No image rendering or inference; duplicate hashes were computed during data-only grouping.",
    }
    write_json(output, result)
    print(
        json.dumps(
            {
                "candidates": len(chosen),
                "reserves": len(result["reserves"]),
                "video_ids": result["video_ids"],
            },
            indent=2,
        )
    )


def export_candidates(archive, audit, selection, output):
    from .prepare import prepare

    output = Path(output)
    if output.exists():
        raise FileExistsError("Do not replace existing lossless exports")
    queue = json.loads(Path(selection).read_text(encoding="utf-8"))
    return prepare(
        archive,
        audit,
        output,
        [(r["video_id"], r["focus"]) for r in queue["candidates"]],
    )


def camera_shifts(video, gt):
    import cv2

    shifts = [{"shift": [0.0, 0.0], "features": 0}]
    previous = cv2.imread(str(video.rgb_paths[0]), cv2.IMREAD_GRAYSCALE)
    for t, path in enumerate(video.rgb_paths[1:], start=1):
        current = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        background = np.full(previous.shape, 255, np.uint8)
        for obj in gt[t - 1]:
            background[obj.mask] = 0
        points = cv2.goodFeaturesToTrack(previous, 150, 0.02, 8, mask=background)
        values = []
        if points is not None:
            moved, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points, None)
            if moved is not None:
                delta = (moved - points).reshape(-1, 2)
                values = delta[status.flatten().astype(bool)]
        shift = np.median(values, axis=0).tolist() if len(values) >= 8 else [0.0, 0.0]
        shifts.append({"shift": shift, "features": len(values)})
        previous = current
    return shifts


def frame_tile(video, gt, t, width=280):
    image = Image.open(video.rgb_paths[t]).convert("RGB")
    draw = ImageDraw.Draw(image)
    for obj in gt[t]:
        color = (50, 235, 150) if obj.category == "person" else (255, 180, 60)
        draw.rectangle(tuple(obj.box.astype(int)), outline=color, width=2)
        draw.text(
            (int(obj.box[0]), max(0, int(obj.box[1]) - 12)),
            f"{obj.category} GT{obj.identity}",
            fill=color,
        )
    image.thumbnail((width, 180))
    tile = Image.new("RGB", (width, 210), (18, 25, 31))
    tile.paste(image, (0, 26))
    ImageDraw.Draw(tile).text(
        (7, 6),
        f"{video.video_id} | step {t}",
        fill="white",
        font=ImageFont.load_default(size=15),
    )
    return tile


def screen(data_root, queue_path, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Preserve prior candidate screens")
    output.mkdir(parents=True)
    queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    videos, records, _ = read_manifest(data_root, queue["video_ids"])
    all_rows, metadata = [], []
    for video, record in zip(videos, records):
        gt = load_ground_truth(data_root, record)
        n = len(gt)
        shifts = camera_shifts(video, gt)
        identities = {o.identity: o.category for frame in gt for o in frame}
        video_rows = []
        for identity, category in identities.items():
            objects = [
                next((o for o in frame if o.identity == identity), None) for frame in gt
            ]
            centers = [
                np.array(np.nonzero(o.mask)[::-1]).mean(axis=1) if o else None
                for o in objects
            ]
            for t in range(10, n - 30):
                obj = objects[t]
                if obj is None or sum(o is not None for o in objects[:t]) < 3:
                    continue
                diag = max(1.0, float(np.linalg.norm(obj.box[2:] - obj.box[:2])))
                velocity = (
                    centers[t] - centers[t - 1] - shifts[t]["shift"]
                    if centers[t - 1] is not None
                    else np.zeros(2)
                )
                prior = (
                    centers[t - 1] - centers[t - 2] - shifts[t - 1]["shift"]
                    if centers[t - 1] is not None and centers[t - 2] is not None
                    else np.zeros(2)
                )
                speed, before = np.linalg.norm(velocity), np.linalg.norm(prior)
                angle = (
                    float(
                        np.degrees(
                            np.arccos(
                                np.clip(
                                    np.dot(velocity, prior) / max(speed * before, 1e-9),
                                    -1,
                                    1,
                                )
                            )
                        )
                    )
                    if min(speed, before) > 1
                    else 0.0
                )
                gap = 0
                for o in reversed(objects[:t]):
                    if o is not None:
                        break
                    gap += 1
                areas = [
                    int(o.mask.sum())
                    for o in objects[max(0, t - 8) : t]
                    if o is not None
                ]
                other = [
                    o
                    for o in gt[t]
                    if o.identity != identity and o.category == category
                ]
                area = int(obj.mask.sum())
                row = {
                    "video_id": video.video_id,
                    "gt_id": identity,
                    "category": category,
                    "frame": t,
                    "frames": n,
                    "area": area,
                    "area_fraction": area / (video.height * video.width),
                    "gap_before": gap,
                    "visible_followup": sum(
                        o is not None for o in objects[t + 1 : t + 31]
                    ),
                    "prefix_visible": sum(o is not None for o in objects[:t]),
                    "relative_acceleration": float(
                        np.linalg.norm(velocity - prior) / diag
                    ),
                    "relative_speed": float(speed / diag),
                    "turn_angle": angle,
                    "background_flow": shifts[t],
                    "same_class_gt_overlap": max(
                        (box_iou(obj.box, o.box) for o in other), default=0.0
                    ),
                    "same_class_nearby": int(
                        sum(
                            np.linalg.norm(
                                (o.box[:2] + o.box[2:]) / 2
                                - (obj.box[:2] + obj.box[2:]) / 2
                            )
                            / diag
                            < 1.5
                            for o in other
                        )
                    ),
                    "area_ratio_to_prefix_median": area
                    / max(float(np.median(areas)) if areas else area, 1),
                }
                video_rows.append(row)
        all_rows += video_rows
        important = {0, 10, n - 1}
        for field in ("relative_acceleration", "same_class_gt_overlap", "gap_before"):
            if video_rows:
                important.add(max(video_rows, key=lambda r: r[field])["frame"])
        indices = sorted(important)
        sheet = Image.new("RGB", (280 * len(indices), 210), (18, 25, 31))
        for i, t in enumerate(indices):
            sheet.paste(frame_tile(video, gt, t), (280 * i, 0))
        sheet.save(output / f"{video.video_id}-overview.jpg", quality=92)
        metadata.append(
            {
                "video_id": video.video_id,
                "frames": n,
                "tracks": identities,
                "overview_steps": indices,
                "overview": f"{video.video_id}-overview.jpg",
                "candidate_rows": len(video_rows),
            }
        )
        print("GT screen", video.video_id, len(video_rows), "rows", flush=True)
    write_json(
        output / "gt-features.json",
        {
            "role": "GT/RGB-only ranking hints, no proof of occlusion or model quality",
            "rows": all_rows,
            "videos": metadata,
        },
    )
    write_json(
        output / "provenance.json",
        {
            "queue_sha256": digest(queue_path),
            "data_manifest_sha256": digest(Path(data_root) / "manifest.json"),
            "source_sha256": digest(Path(__file__)),
            "H_R_run": False,
        },
    )
    # Compact contact sheets for actual visual review, four videos per sheet.
    for start in range(0, len(metadata), 4):
        chunk = metadata[start : start + 4]
        canvas = Image.new("RGB", (1680, 230 * len(chunk)), (18, 25, 31))
        for i, row in enumerate(chunk):
            image = Image.open(output / row["overview"])
            canvas.paste(image, (0, i * 230))
        canvas.save(output / f"contact-{start//4+1:02d}.jpg", quality=94)
    print("GT screening complete", len(videos), "videos", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("queue", "export", "screen"))
    parser.add_argument("--split", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.action == "queue":
        choose_candidates(args.split, args.audit, args.output)
    elif args.action == "export":
        export_candidates(args.archive, args.audit, args.queue, args.output)
    else:
        screen(args.data_root, args.queue, args.output)


if __name__ == "__main__":
    main()
