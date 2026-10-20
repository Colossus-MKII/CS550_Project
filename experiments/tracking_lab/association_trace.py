"""Read-only probes of the INSTALLED ByteTrack assignment calls.

No reimplementation of the tracker: call upstream once with the original
arrays, then copy its costs/results for teaching and diagnosis. This scoped
module probe is for our sequential local runner, NOT concurrent tracker jobs.
The three assignment stages below are checked against pinned Ultralytics.
"""

from contextlib import contextmanager

import numpy as np


@contextmanager
def observe_assignments(category, selected, external_ids):
    from ultralytics.trackers.utils import matching

    original_iou = matching.iou_distance
    original_assignment = matching.linear_assignment
    records, pending = [], {}
    stages = ("high_confidence", "low_confidence", "unconfirmed")

    def track_record(track):
        return {
            "internal_id": int(track.track_id),
            "external_id": external_ids.get((category, int(track.track_id))),
            "state": int(track.state),
            "predicted_box": track.xyxy.tolist(),
            "mean": track.mean.tolist() if track.mean is not None else None,
            "covariance": (
                track.covariance.tolist() if track.covariance is not None else None
            ),
        }

    def iou_probe(tracks, detections):
        costs = original_iou(tracks, detections)
        # Snapshot BEFORE update() mutates the tracks. Duplicate-removal also
        # calls iou_distance, but no assignment follows that final call.
        pending.clear()
        pending.update(
            tracks=[track_record(track) for track in tracks],
            detections=(
                [
                    {
                        "detector_index": int(selected[int(det.idx)].identity),
                        "box": det.xyxy.tolist(),
                        "score": float(det.score),
                    }
                    for det in detections
                ]
                if len(records) < 3
                else []
            ),
            raw_iou_cost=costs.tolist(),
        )
        return costs

    def assignment_probe(costs, thresh, use_lap=True):
        result = original_assignment(costs, thresh, use_lap=use_lap)
        index = len(records)
        if index >= len(stages):
            raise RuntimeError("Upstream ByteTrack assignment layout changed")
        if costs.shape != (len(pending["tracks"]), len(pending["detections"])):
            raise RuntimeError("Assignment probe lost its candidate mapping")
        matches, missing_tracks, missing_detections = result
        records.append(
            {
                "stage": stages[index],
                "threshold": float(thresh),
                "shape": list(costs.shape),
                **pending,
                "assignment_cost": costs.tolist(),
                "matches": np.asarray(matches, dtype=int).reshape(-1, 2).tolist(),
                "unmatched_tracks": [int(i) for i in missing_tracks],
                "unmatched_detections": [int(i) for i in missing_detections],
            }
        )
        return result

    matching.iou_distance, matching.linear_assignment = iou_probe, assignment_probe
    try:
        yield records
        if len(records) != 3:
            raise RuntimeError("Expected three native ByteTrack assignment stages")
    finally:
        matching.iou_distance = original_iou
        matching.linear_assignment = original_assignment
