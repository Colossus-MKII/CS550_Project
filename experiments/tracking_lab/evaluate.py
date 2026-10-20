"""Class-aware mask HOTA / IDF1 / CLEAR using the pinned official TrackEval.

No handwritten substitute for HOTA or IDF1. This adapter supplies binary-mask
IoU matrices in original exported coordinates. Metrics first combine sequences
within each class using upstream rules, then average the five classes equally.
"""

from contextlib import redirect_stdout
import importlib
import io
from pathlib import Path
import subprocess
import sys

import numpy as np

from . import ROOT
from .common import CLASSES, Instance, mask_iou

EVAL_REV = "12c8791b303e0a0b50f753af204249e622d0281a"


class NumpyLegacyNames:
    """Module-local NumPy 2 compatibility, NOT a global NumPy monkey patch.

    This pinned older TrackEval uses the removed np.float / np.int aliases.
    Forward all operations to NumPy, mapping only aliases to original builtins.
    No metric arithmetic, matching logic or upstream file is modified.
    """

    float = float
    int = int

    def __getattr__(self, name):
        return getattr(np, name)


def metric_objects(root=None):
    root = Path(root or ROOT / "external/TrackEval").resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != EVAL_REV:
        raise RuntimeError(f"TrackEval must be pinned to {EVAL_REV}")
    if subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only"], text=True
    ).strip():
        raise RuntimeError("TrackEval source has local modifications")
    sys.path.insert(0, str(root)) if str(root) not in sys.path else None
    # The root package optionally imports BURST; its missing optional dependency
    # is irrelevant to direct mask similarity evaluation, not a scoring fallback.
    with redirect_stdout(io.StringIO()):
        from trackeval.metrics import HOTA, Identity, CLEAR
    if Path(sys.modules["trackeval"].__file__).resolve().parent != root / "trackeval":
        raise RuntimeError("A different TrackEval package shadowed the pinned checkout")
    for slug in ("hota", "identity", "clear"):
        importlib.import_module("trackeval.metrics." + slug).np = NumpyLegacyNames()
    return {
        "HOTA": HOTA(),
        "Identity": Identity({"THRESHOLD": 0.5, "PRINT_CONFIG": False}),
        "CLEAR": CLEAR({"THRESHOLD": 0.5, "PRINT_CONFIG": False}),
    }


def similarity_data(gt, prediction, category):
    if len(gt) != len(prediction):
        raise ValueError("Prediction and GT frame counts differ")
    g = [[o for o in objects if o.category == category] for objects in gt]
    p = [[o for o in objects if o.category == category] for objects in prediction]
    gids = {
        key: i
        for i, key in enumerate(sorted({o.identity for frame in g for o in frame}))
    }
    pids = {
        key: i
        for i, key in enumerate(sorted({o.identity for frame in p for o in frame}))
    }
    for frame in g + p:
        if len({o.identity for o in frame}) != len(frame):
            raise ValueError("Duplicate IDs in metric input")
    return {
        "num_timesteps": len(gt),
        "num_gt_ids": len(gids),
        "num_tracker_ids": len(pids),
        "num_gt_dets": sum(map(len, g)),
        "num_tracker_dets": sum(map(len, p)),
        "gt_ids": [
            np.array([gids[o.identity] for o in frame], dtype=int) for frame in g
        ],
        "tracker_ids": [
            np.array([pids[o.identity] for o in frame], dtype=int) for frame in p
        ],
        "similarity_scores": [
            np.array(
                [[mask_iou(a.mask, b.mask) for b in pf] for a in gf], dtype=float
            ).reshape(len(gf), len(pf))
            for gf, pf in zip(g, p)
        ],
    }


def serial(value):
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def compact(raw):
    return {
        "HOTA": float(np.mean(raw["HOTA"]["HOTA"])),
        "DetA": float(np.mean(raw["HOTA"]["DetA"])),
        "AssA": float(np.mean(raw["HOTA"]["AssA"])),
        "IDF1": float(raw["Identity"]["IDF1"]),
        "TP": int(raw["CLEAR"]["CLR_TP"]),
        "FP": int(raw["CLEAR"]["CLR_FP"]),
        "FN": int(raw["CLEAR"]["CLR_FN"]),
        "IDSW": int(raw["CLEAR"]["IDSW"]),
    }


def evaluate_all(videos, metrics=None):
    """videos maps video ID -> (GT frames, prediction frames). Scores in [0,1]."""
    metrics = metrics or metric_objects()
    per_video = {}
    combined = {name: {} for name in metrics}
    per_class = {}
    for category in CLASSES:
        by_video = {name: {} for name in metrics}
        gt_count = pred_count = 0
        for key, (gt, pred) in videos.items():
            data = similarity_data(gt, pred, category)
            gt_count += data["num_gt_dets"]
            pred_count += data["num_tracker_dets"]
            raw = {name: metric.eval_sequence(data) for name, metric in metrics.items()}
            for name in metrics:
                by_video[name][str(key)] = raw[name]
            per_video.setdefault(str(key), {})[category] = {
                "scores": compact(raw),
                "raw": serial(raw),
                "gt_detections": data["num_gt_dets"],
                "predicted_detections": data["num_tracker_dets"],
            }
        if gt_count or pred_count:
            raw = {
                name: metric.combine_sequences(by_video[name])
                for name, metric in metrics.items()
            }
            for name in metrics:
                combined[name][category] = raw[name]
            per_class[category] = {
                "scores": compact(raw),
                "raw": serial(raw),
                "gt_detections": gt_count,
                "predicted_detections": pred_count,
            }
    if not per_class:
        raise ValueError("No GT or predictions to evaluate")
    macro = {
        name: metric.combine_classes_class_averaged(combined[name])
        for name, metric in metrics.items()
    }
    return {
        "macro": compact(macro),
        "per_class": per_class,
        "per_video": per_video,
        "macro_raw": serial(macro),
        "trackeval_revision": EVAL_REV,
        "aggregation": "official combine_sequences within class, then equal weight across present classes",
        "thresholds": {
            "HOTA": np.arange(0.05, 0.99, 0.05).tolist(),
            "Identity": 0.5,
            "CLEAR": 0.5,
        },
        "count_scope": "FP/FN/TP/IDSW summed over classes; quality metrics class-macro; empty GT/pred classes excluded",
        "coordinates": "native exported-frame masks; no GT-dependent model prompts",
    }


def self_checks(metrics=None):
    """Analytic evaluator checks run BEFORE any actual model scoring."""
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True

    def obj(key=1, category="person"):
        return Instance(key, category, np.array([2, 2, 6, 6]), mask.copy())

    gt = [[obj()] for _ in range(4)]
    cases = {
        "perfect": (gt, {"HOTA": 1.0, "IDF1": 1.0, "FP": 0, "FN": 0, "IDSW": 0}),
        "one_miss": (
            [[obj()], [obj()], [], [obj()]],
            {"HOTA": 0.75, "IDF1": 6 / 7, "FP": 0, "FN": 1, "IDSW": 0},
        ),
        "id_switch": (
            [[obj(1)], [obj(1)], [obj(2)], [obj(2)]],
            {"HOTA": np.sqrt(0.5), "IDF1": 0.5, "FP": 0, "FN": 0, "IDSW": 1},
        ),
        "wrong_class": (
            [[obj(category="dog")] for _ in range(4)],
            {"HOTA": 0.0, "IDF1": 0.0, "FP": 4, "FN": 4, "IDSW": 0},
        ),
        "empty": (
            [[], [], [], []],
            {"HOTA": 0.0, "IDF1": 0.0, "FP": 0, "FN": 4, "IDSW": 0},
        ),
    }
    metrics = metrics or metric_objects()
    results = {}
    for name, (prediction, expected) in cases.items():
        actual = evaluate_all({"synthetic": (gt, prediction)}, metrics)["macro"]
        for field, value in expected.items():
            if not np.isclose(actual[field], value, atol=1e-8):
                raise AssertionError((name, field, actual[field], value))
        results[name] = {"passed": True, "scores": actual}
    return results
