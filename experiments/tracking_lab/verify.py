"""Verify saved inputs, A0 mask/ID replay, B0 schedule and all official metrics.

No checkpoint is loaded. GT never enters the A0 replay or B0 event validation.
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .bytetrack import run_bytetrack
from .common import digest, load_predictions, write_json
from .dataset import load_ground_truth, read_manifest
from .evaluate import evaluate_all, metric_objects
from .runtime import resolve_data_root


def verify(output, data_root=None, trackeval_root=None, write_record=False):
    output = Path(output).resolve()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    config = summary["configuration"]
    inputs = json.loads((output / "input-manifest.json").read_text(encoding="utf-8"))
    scores = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    samples = resolve_data_root(output, summary, data_root)
    metrics = metric_objects(trackeval_root)
    for row in inputs["files"]:
        if digest(samples / row["file"]) != row["sha256"]:
            raise AssertionError("Input changed: " + row["file"])
    for name, expected in summary["source_files"].items():
        assert digest(output / "code" / (name + ".txt")) == expected
    videos, records, _ = read_manifest(samples, summary["selection"]["video_ids"])
    evaluation = {"A0": {}, "B0": {}}
    frames = 0
    calls_b = 0
    images = 0
    for video, record in zip(videos, records):
        folder = output / str(video.video_id)
        observations = load_predictions(folder / "YOLO")
        a = load_predictions(folder / "A0")
        b = load_predictions(folder / "B0")
        replay, _ = run_bytetrack(observations, (video.height, video.width), config)
        assert len(a) == len(b) == len(observations) == len(video.rgb_paths)
        for expected, actual in zip(a, replay):
            assert len(expected) == len(actual)
            for x, y in zip(expected, actual):
                assert (x.identity, x.category, x.score) == (
                    y.identity,
                    y.category,
                    y.score,
                )
                np.testing.assert_array_equal(x.mask, y.mask)
                np.testing.assert_array_equal(x.box, y.box)
        events = json.loads((folder / "B0/event-log.json").read_text(encoding="utf-8"))
        assert len(events) == len(b)
        for t, event in enumerate(events):
            assert event["frame"] == t
            assert event["detector_called"] == (t % config["discovery_interval"] == 0)
            calls_b += event["detector_called"]
            assert set(event["output_ids"]) == {o.identity for o in b[t]}
            assert set(event["output_ids"]) <= set(event["active_ids"])
            for action in event["actions"]:
                if action["action"] in ("discover", "refresh"):
                    assert event["detector_called"]
                    detector = next(
                        o
                        for o in observations[t]
                        if o.identity == action["detector_index"]
                    )
                    assert detector.score >= config["sam_prompt_conf"]
            for obj in a[t] + b[t]:
                assert obj.mask.shape == (video.height, video.width)
            if summary["status"] == "completed":
                image = cv2.imread(str(folder / "visuals" / f"{t:05d}.jpg"))
                assert image is not None and image.shape[:2] == (
                    (video.height + 32) * 3,
                    video.width * 2,
                )
                images += 1
        if summary["status"] == "completed":
            cap = cv2.VideoCapture(str(folder / "comparison.mp4"))
            try:
                assert cap.isOpened()
                assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == len(b)
                assert cap.get(cv2.CAP_PROP_FPS) == config["browse_fps"]
            finally:
                cap.release()
        gt = load_ground_truth(samples, record)
        evaluation["A0"][str(video.video_id)] = (gt, a)
        evaluation["B0"][str(video.video_id)] = (gt, b)
        frames += len(gt)
    for method in evaluation:
        # Compare every video/class/threshold array, not only the grand mean.
        assert evaluate_all(evaluation[method], metrics) == scores[method], (
            method + " scores changed"
        )
    result = {
        "status": "passed",
        "source_snapshots": len(summary["source_files"]),
        "verified_input_files": len(inputs["files"]),
        "RGB_steps": frames,
        "A0_masks_and_IDs": "exact replay",
        "metrics": "all per-video/class/threshold results match",
        "B0_detector_calls_used": calls_b,
        "visualized_frames": images,
        "videos": len(videos),
    }
    if write_record:
        write_json(output / "verification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--trackeval-root", type=Path)
    parser.add_argument("--write-record", action="store_true")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            verify(args.output, args.data_root, args.trackeval_root, args.write_record),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
