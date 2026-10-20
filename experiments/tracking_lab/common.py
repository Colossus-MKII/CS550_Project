"""Small, model-independent data structures and geometry utilities.

Boxes use [x1,y1,x2,y2] with EXCLUSIVE right/bottom edges. Masks always have
the original exported H,W. Tracking IDs are video-wide, not GT channel IDs.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

CLASSES = ("person", "dog", "cat", "horse", "car")
COCO = {"person": 0, "car": 2, "cat": 15, "dog": 16, "horse": 17}


@dataclass
class Instance:
    identity: int
    category: str
    box: np.ndarray
    mask: np.ndarray
    score: float = 1.0


def digest(path):
    result = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def mask_box(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return np.zeros(4, dtype=np.float32)
    return np.array([xs.min(), ys.min(), xs.max() + 1, ys.max() + 1], dtype=np.float32)


def box_iou(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    intersection = np.maximum(
        0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2])
    ).prod()
    union = (
        np.maximum(0, a[2:] - a[:2]).prod()
        + np.maximum(0, b[2:] - b[:2]).prod()
        - intersection
    )
    return float(intersection / union) if union > 0 else 0.0


def mask_iou(a, b):
    if a.shape != b.shape:
        raise ValueError("Mask coordinates differ")
    union = np.count_nonzero(a | b)
    return float(np.count_nonzero(a & b) / union) if union else 0.0


def associate(tracks, detections, threshold):
    """Class-aware, gated one-to-one box matching; never use GT here.

    The large valid-edge bonus maximizes the NUMBER of threshold-valid matches
    before maximizing IoU. Matching all edges then filtering can lose valid pairs.
    """
    similarity = np.array(
        [
            [
                box_iou(a.box, b.box) if a.category == b.category else -1
                for b in detections
            ]
            for a in tracks
        ],
        dtype=float,
    )
    if not tracks or not detections:
        return [], list(range(len(tracks))), list(range(len(detections)))
    valid = similarity >= threshold
    score = valid * (min(len(tracks), len(detections)) + 1 + np.maximum(0, similarity))
    rows, cols = linear_sum_assignment(-score)
    matches = [(int(r), int(c)) for r, c in zip(rows, cols) if valid[r, c]]
    return (
        matches,
        [i for i in range(len(tracks)) if i not in {a for a, _ in matches}],
        [i for i in range(len(detections)) if i not in {b for _, b in matches}],
    )


def save_predictions(folder, frames, shape):
    """JSON is inspectable; binary masks are separate non-pickled NPZ arrays."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, objects in enumerate(frames):
        ids = [o.identity for o in objects]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate prediction IDs in one frame")
        masks = (
            np.stack([o.mask for o in objects])
            if objects
            else np.zeros((0, *shape), dtype=bool)
        )
        if masks.shape[1:] != tuple(shape):
            raise ValueError("Masks must remain in exported coordinates")
        np.savez_compressed(folder / f"{t:05d}.npz", masks=masks)
        rows.append(
            {
                "frame": t,
                "mask_file": f"{t:05d}.npz",
                "objects": [
                    {
                        "id": o.identity,
                        "category": o.category,
                        "score": o.score,
                        "box_xyxy": o.box.tolist(),
                        "mask_area": int(o.mask.sum()),
                    }
                    for o in objects
                ],
            }
        )
    write_json(folder / "predictions.json", rows)


def load_predictions(folder):
    folder = Path(folder)
    rows = json.loads((folder / "predictions.json").read_text(encoding="utf-8"))
    result = []
    for t, row in enumerate(rows):
        if t != row["frame"]:
            raise ValueError("Frame order changed")
        with np.load(folder / row["mask_file"], allow_pickle=False) as archive:
            masks = archive["masks"]
        if len(masks) != len(row["objects"]):
            raise ValueError("Mask/object count mismatch")
        result.append(
            [
                Instance(
                    o["id"],
                    o["category"],
                    np.asarray(o["box_xyxy"], dtype=np.float32),
                    m.astype(bool),
                    o["score"],
                )
                for o, m in zip(row["objects"], masks)
            ]
        )
    return result
