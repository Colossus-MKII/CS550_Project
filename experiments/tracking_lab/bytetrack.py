"""A0: separate official ByteTrack instances per class, with shared observations.

ByteTrack predicts/associates boxes; it does NOT generate pixel masks. The
adapter below carries ORIGINAL detection indices through both confidence
filters, so the output index selects the correct YOLO mask. Nearest-box matching
is not used. The Kalman filter and association algorithm are unmodified.
"""

from types import SimpleNamespace

import numpy as np

from .common import CLASSES, COCO, Instance


class DetectionBatch:
    """Minimal tracker input whose slicing preserves the original row indices."""

    def __init__(self, values, indices=None):
        self.values = np.asarray(values, dtype=np.float32).reshape(-1, 6)
        self.indices = (
            np.arange(len(self.values))
            if indices is None
            else np.asarray(indices).reshape(-1)
        )

    def __len__(self):
        return len(self.values)

    def __getitem__(self, key):
        return DetectionBatch(self.values[key], self.indices[key])

    @property
    def conf(self):
        return self.values[:, 4]

    @property
    def cls(self):
        return self.values[:, 5]

    @property
    def xywh(self):
        result = self.values[:, :4].copy()
        result[:, 2:] -= result[:, :2]
        result[:, :2] += result[:, 2:] / 2
        return result


def run_bytetrack(detections, shape, config):
    from . import configure_runtime

    configure_runtime()
    from ultralytics.trackers.byte_tracker import BYTETracker, STrack

    class IndexedBYTETracker(BYTETracker):
        def init_track(self, results, img=None):
            # Upstream v8.3.221 assigns arange AFTER high/low slicing. Retain
            # original class-subset indices instead; all other logic is inherited.
            boxes = np.concatenate([results.xywh, results.indices[:, None]], axis=1)
            return [
                STrack(box, score, category)
                for box, score, category in zip(boxes, results.conf, results.cls)
            ]

    # Construct all trackers before updating any: upstream constructors reset a
    # shared ID counter. Our external map additionally guarantees video-wide IDs.
    # 30 is upstream's buffer normalization constant, NOT assumed source FPS:
    # max_time_lost = int(frame_rate/30 * track_buffer), hence 30 exported steps.
    trackers = {
        category: IndexedBYTETracker(
            SimpleNamespace(**config["bytetrack"]), frame_rate=30
        )
        for category in CLASSES
    }
    external = {}
    next_id = 1
    frames = []
    trace = []

    def public_id(category, internal):
        nonlocal next_id
        key = (category, int(internal))
        if key not in external:
            external[key] = next_id
            next_id += 1
        return external[key]

    for t, observations in enumerate(detections):
        objects = []
        states = []
        for category, tracker in trackers.items():
            selected = [o for o in observations if o.category == category]
            values = np.array(
                [[*o.box, o.score, COCO[category]] for o in selected], dtype=np.float32
            ).reshape(-1, 6)
            tracked = tracker.update(
                DetectionBatch(values)
            )  # Also advance empty frames.
            for row in tracked:
                index = int(row[-1])
                source = selected[index]
                objects.append(
                    Instance(
                        public_id(category, row[4]),
                        category,
                        source.box.copy(),
                        source.mask.copy(),
                        source.score,
                    )
                )
            # This is diagnostic state, not additional predictions for lost tracks.
            for tr in tracker.tracked_stracks + tracker.lost_stracks:
                states.append(
                    {
                        "id": public_id(category, tr.track_id),
                        "category": category,
                        "state": int(tr.state),
                        "activated": bool(tr.is_activated),
                        "box_xyxy": tr.xyxy.tolist(),
                        "mean": tr.mean.tolist(),
                        "covariance_diagonal": np.diag(tr.covariance).tolist(),
                    }
                )
        frames.append(objects)
        trace.append({"frame": t, "states": states})
    return frames, trace
