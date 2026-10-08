"""Canonical frame records and uncompressed COCO (column-major) mask RLE."""

import math
from collections.abc import Iterable


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def encode_rle(mask):
    """Encode a rectangular sequence of binary rows, beginning with a zero run."""
    rows = [list(row) for row in mask]
    height = len(rows)
    width = len(rows[0]) if height else 0
    if not height or not width or any(len(row) != width for row in rows):
        raise ValueError("mask must be a nonempty rectangle")
    counts, previous, run = [], 0, 0
    for column in range(width):
        for row in range(height):
            value = rows[row][column]
            if value not in (0, 1):
                raise ValueError("mask pixels must be binary")
            value = int(value)
            if value == previous:
                run += 1
            else:
                counts.append(run)
                previous, run = value, 1
    counts.append(run)
    return {"size": [height, width], "counts": counts}


def decode_rle(rle):
    size, counts = rle["size"], rle["counts"]
    if len(size) != 2:
        raise ValueError("RLE size must be [height, width]")
    height, width = size
    _integer(height, "height", 1)
    _integer(width, "width", 1)
    if not isinstance(counts, list) or not counts:
        raise ValueError("counts must be a nonempty uncompressed RLE list")
    for count in counts:
        _integer(count, "run length")
    if sum(counts) != height * width:
        raise ValueError("RLE counts do not cover the image")
    rows = [[0] * width for _ in range(height)]
    offset = 0
    for index, count in enumerate(counts):
        for position in range(offset, offset + count):
            rows[position % height][position // height] = index % 2
        offset += count
    return rows


def validate_frame(record):
    """Validate dimensions, masks and unique positive track IDs within a frame."""
    _integer(record["frame_idx"], "frame_idx")
    height, width = record["image_size"]
    _integer(height, "height", 1)
    _integer(width, "width", 1)
    timestamp = record["timestamp_s"]
    if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("timestamp_s must be finite and nonnegative")
    seen = set()
    for obj in record["objects"]:
        _integer(obj["object_id"], "object_id", 1)
        _integer(obj["category_id"], "category_id")
        if obj["object_id"] in seen:
            raise ValueError("duplicate object_id in a frame")
        seen.add(obj["object_id"])
        if not isinstance(obj["category_name"], str) or not obj["category_name"]:
            raise ValueError("category_name must be a nonempty string")
        score = obj["score"]
        if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("score must be finite and in [0, 1]")
        if obj["mask"]["size"] != [height, width]:
            raise ValueError("mask resolution must equal frame resolution")
        decode_rle(obj["mask"])
    return record


def group_tracks(records: Iterable[dict], frame_count: int, category_map: dict):
    """Prepare track sequences for VIS export; fail on missing frames or class drift."""
    _integer(frame_count, "frame_count", 1)
    tracks, seen_frames, last_frame = {}, set(), -1
    for record in records:
        validate_frame(record)
        frame_idx = record["frame_idx"]
        if frame_idx >= frame_count or frame_idx <= last_frame:
            raise ValueError("frames must be ordered, unique, and within frame_count")
        last_frame = frame_idx
        seen_frames.add(frame_idx)
        for obj in record["objects"]:
            source_class = str(obj["category_id"])
            if source_class not in category_map:
                raise ValueError(f"missing category mapping for class {source_class}")
            dataset_class = category_map[source_class]
            _integer(dataset_class, "dataset category_id", 1)
            track = tracks.setdefault(obj["object_id"], {
                "category_id": dataset_class,
                "segmentations": [None] * frame_count,
                "scores": [],
            })
            if track["category_id"] != dataset_class:
                raise ValueError("a track changed category; resolve class votes before export")
            track["segmentations"][frame_idx] = obj["mask"]
            track["scores"].append(obj["score"])
    if len(seen_frames) != frame_count:
        raise ValueError("records must include every frame, including empty frames")
    return tracks

