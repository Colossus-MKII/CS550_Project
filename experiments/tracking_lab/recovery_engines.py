"""Steppable A/B adapters for the recovery pilot.

The original stage-1 functions remain reference implementations. With no
correction these adapters must replay their saved prefix masks and IDs exactly.
Only `correct()` / the correction block differs between H and R.
"""

import copy
from contextlib import nullcontext
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from .common import CLASSES, COCO, Instance, associate, box_iou, mask_box
from .bytetrack import DetectionBatch
from .sam_baseline import Target, init_png_state, propagate_one
from .recovery_state import clone_tree, reset_sam_target, sam_history_summary


@dataclass
class Correction:
    identity: int
    category: str
    box: np.ndarray
    score: float
    detector_index: int | None
    reset: bool


class ByteEngine:
    def __init__(self, config, association_diagnostics=False):
        from . import configure_runtime

        configure_runtime()
        from ultralytics.trackers.byte_tracker import BYTETracker, STrack

        class IndexedTracker(BYTETracker):
            def init_track(self, results, img=None):
                boxes = np.concatenate([results.xywh, results.indices[:, None]], axis=1)
                return [
                    STrack(box, score, category)
                    for box, score, category in zip(boxes, results.conf, results.cls)
                ]

        self.trackers = {
            c: IndexedTracker(SimpleNamespace(**config["bytetrack"]), frame_rate=30)
            for c in CLASSES
        }
        self.external = {}
        self.next_id = 1
        self.counter = 0
        self.frame = -1
        self.association_diagnostics = association_diagnostics

    def public_id(self, category, internal):
        key = category, int(internal)
        if key not in self.external:
            self.external[key] = self.next_id
            self.next_id += 1
        return self.external[key]

    def find(self, identity):
        for category, tracker in self.trackers.items():
            for track in tracker.tracked_stracks + tracker.lost_stracks:
                if self.external.get((category, int(track.track_id))) == identity:
                    return tracker, track
        raise ValueError("Designated ByteTrack state no longer exists")

    def eligible(self, identity):
        try:
            _, track = self.find(identity)
            return bool(track.is_activated and track.mean is not None)
        except ValueError:
            return False

    def fork(self):
        return copy.deepcopy(self)

    @staticmethod
    def snapshot(track):
        return {
            "mean": track.mean.tolist(),
            "covariance": track.covariance.tolist(),
            "box_xyxy": track.xyxy.tolist(),
            "frame_id": track.frame_id,
            "start_frame": track.start_frame,
            "state": int(track.state),
            "activated": bool(track.is_activated),
            "internal_id": int(track.track_id),
            "tracklet_len": track.tracklet_len,
        }

    def step(self, t, observations, correction=None):
        """Advance once. At correction, route one box explicitly, not twice.

        Detach ONLY the designated track from automatic association at t. Other
        tracks update normally. H predicts once then performs the ordinary KF
        measurement update; R initializes the KF at t. Future steps are native.
        """
        from ultralytics.trackers.basetrack import BaseTrack, TrackState

        if t != self.frame + 1:
            raise ValueError("ByteEngine requires consecutive forward steps")
        BaseTrack._count = (
            self.counter
        )  # Branch-local copy of upstream's global ID counter.
        saved = audit = None
        if correction:
            tracker, saved = self.find(correction.identity)
            if not self.eligible(correction.identity):
                raise ValueError("Cannot retain uninitialized ByteTrack state")
            audit = {"before": self.snapshot(saved)}
            tracker.tracked_stracks = [
                x for x in tracker.tracked_stracks if x is not saved
            ]
            tracker.lost_stracks = [x for x in tracker.lost_stracks if x is not saved]
        objects, states, assignments = [], [], []
        for category, tracker in self.trackers.items():
            # Record native one-step motion forecasts without mutating state.
            forecasts = {}
            for track in tracker.tracked_stracks + tracker.lost_stracks:
                predicted = copy.deepcopy(track)
                predicted.predict()
                forecasts[int(track.track_id)] = predicted.xyxy.tolist()
            selected = [
                o
                for o in observations
                if o.category == category
                and not (correction and o.identity == correction.detector_index)
            ]
            values = np.asarray(
                [[*o.box, o.score, COCO[category]] for o in selected], np.float32
            ).reshape(-1, 6)
            from .association_trace import observe_assignments

            probe = (
                observe_assignments(category, selected, self.external)
                if self.association_diagnostics
                else nullcontext([])
            )
            with probe as stages:
                tracked = tracker.update(DetectionBatch(values))
            if self.association_diagnostics:
                assignments.append({"category": category, "stages": stages})
            for row in tracked:
                source = selected[int(row[-1])]
                objects.append(
                    Instance(
                        self.public_id(category, row[4]),
                        category,
                        source.box.copy(),
                        source.mask.copy(),
                        source.score,
                    )
                )
            if correction and category == correction.category:
                box = correction.box
                xyah = np.array(
                    [
                        (box[0] + box[2]) / 2,
                        (box[1] + box[3]) / 2,
                        (box[2] - box[0]) / (box[3] - box[1]),
                        box[3] - box[1],
                    ]
                )
                if correction.reset:
                    saved.mean, saved.covariance = saved.kalman_filter.initiate(xyah)
                else:
                    saved.predict()
                    forecasts[int(saved.track_id)] = saved.xyxy.tolist()
                    saved.mean, saved.covariance = saved.kalman_filter.update(
                        saved.mean, saved.covariance, xyah
                    )
                # Identical lifecycle/metadata handling, NOT part of the reset variable.
                saved.frame_id = tracker.frame_id
                saved.tracklet_len += 1
                saved.state = TrackState.Tracked
                saved.is_activated = True
                saved.score = correction.score
                tracker.tracked_stracks.append(saved)
                audit.update(
                    {
                        "after": self.snapshot(saved),
                        "external_id": correction.identity,
                        "correction_updates": 1,
                        "reset": correction.reset,
                        "correction_frame_output": "designated A mask omitted; state-only correction, frame excluded",
                    }
                )
            for track in tracker.tracked_stracks + tracker.lost_stracks:
                states.append(
                    {
                        "id": self.public_id(category, track.track_id),
                        "category": category,
                        **self.snapshot(track),
                        "predicted_box": forecasts.get(int(track.track_id)),
                    }
                )
        self.frame, self.counter = t, BaseTrack._count
        trace = {"frame": t, "states": states, "intervention": audit}
        if self.association_diagnostics:
            trace["assignments"] = assignments
        return objects, trace


class SamEngine:
    def __init__(self, predictor, video, config):
        self.predictor, self.video, self.config = predictor, video, config
        self.state, self.loader = init_png_state(predictor, video)
        self.targets = {}
        self.next_id = 1
        self.frame = -1
        # Optional diagnostic only. Driver freezes (target ID, scheduled step)
        # identically for H/R, independently of either branch's later matching.
        self.skip_refresh = None

    def eligible(self, identity):
        target = self.targets.get(identity)
        return bool(
            target
            and identity in self.state["obj_id_to_idx"]
            and self.frame + 1 - target.last_detection
            <= self.config["sam_retention_steps"]
        )

    def fork(self):
        # Predictor weights are shared READ-ONLY. Every mutable history is copied.
        branch = copy.copy(self)
        branch.state = clone_tree(self.state)
        branch.loader = branch.state["images"]
        branch.targets = copy.deepcopy(self.targets)
        return branch

    def step(self, t, detections, correction=None):
        if t != self.frame + 1:
            raise ValueError("SamEngine requires consecutive forward steps")
        predictor, state, config = self.predictor, self.state, self.config
        actions = []
        if correction and not self.eligible(correction.identity):
            raise ValueError("Cannot retain deleted/expired SAM state")
        for key, target in list(self.targets.items()):
            if t - target.last_detection > config["sam_retention_steps"]:
                predictor.remove_object(state, key, strict=True, need_output=False)
                del self.targets[key]
                actions.append({"action": "retire", "id": key})
        masks = propagate_one(predictor, state, t)
        for key, mask in masks.items():
            if mask.any():
                self.targets[key].box = mask_box(mask)
        prompts = []
        # Trace the actual boxes supplied to SAM, not just scheduled refreshes.
        # This is read-only instrumentation: H/R share detector observations,
        # but their later mask-dependent prompt assignments may diverge.
        prompt_inputs = []
        audit = None
        if correction:
            key = correction.identity
            audit = {
                "before": sam_history_summary(state, key),
                "reset": correction.reset,
            }
            if correction.reset:
                audit["clear"] = reset_sam_target(state, key)
            target = self.targets[key]
            target.box, target.last_detection, target.score = (
                correction.box.copy(),
                t,
                correction.score,
            )
            # A correction supplies a BOX, not a GT mask or replacement class.
            prompts.append((key, correction.box))
            prompt_inputs.append(
                {
                    "id": key,
                    "source": "controlled_correction",
                    "box_xyxy": correction.box.tolist(),
                    "score": correction.score,
                    "detector_index": correction.detector_index,
                }
            )
            actions.append({"action": "controlled_correction", "id": key})
        if t % config["discovery_interval"] == 0:
            if self.skip_refresh and t == self.skip_refresh[1]:
                actions.append(
                    {"action": "skip_refresh_slot", "id": self.skip_refresh[0]}
                )
            observations = [
                o
                for o in detections
                if o.score >= config["sam_prompt_conf"]
                and not (correction and o.identity == correction.detector_index)
            ]
            current = [
                target
                for key, target in self.targets.items()
                if not correction or key != correction.identity
            ]
            matches, _, unmatched = associate(
                current, observations, config["sam_match_iou"]
            )
            for ti, di in matches:
                target, det = current[ti], observations[di]
                if self.skip_refresh == (target.identity, t):
                    # Still consume this native association, so we do not
                    # manufacture a new object from the withheld observation.
                    # Do NOT replace the propagated box with this detector box,
                    # or update score, last_detection, or prompted visual memory.
                    actions.append(
                        {
                            "action": "skipped_refresh",
                            "id": target.identity,
                            "detector_index": det.identity,
                        }
                    )
                    continue
                target.box, target.last_detection, target.score = (
                    det.box.copy(),
                    t,
                    det.score,
                )
                prompts.append((target.identity, det.box))
                prompt_inputs.append(
                    {
                        "id": target.identity,
                        "source": "native_refresh",
                        "box_xyxy": det.box.tolist(),
                        "score": det.score,
                        "detector_index": det.identity,
                    }
                )
                actions.append({"action": "refresh", "id": target.identity})
            for di in unmatched:
                det = observations[di]
                if any(
                    target.category == det.category
                    and box_iou(target.box, det.box) >= config["sam_duplicate_iou"]
                    for target in self.targets.values()
                ):
                    continue
                if len(self.targets) >= 32:
                    raise RuntimeError("Target budget exceeded")
                key = self.next_id
                self.next_id += 1
                self.targets[key] = Target(
                    key, det.category, det.box.copy(), t, det.score
                )
                prompts.append((key, det.box))
                prompt_inputs.append(
                    {
                        "id": key,
                        "source": "native_discover",
                        "box_xyxy": det.box.tolist(),
                        "score": det.score,
                        "detector_index": det.identity,
                    }
                )
                actions.append({"action": "discover", "id": key})
        if prompts:
            if not predictor.add_all_frames_to_correct_as_cond:
                raise RuntimeError("SAM conditioning flag changed")
            for key, box in prompts:
                _, ids, logits = predictor.add_new_points_or_box(
                    state, frame_idx=t, obj_id=key, box=box.astype(np.float32)
                )
            masks = {
                int(key): mask
                for key, mask in zip(ids, (logits > 0).cpu().numpy()[:, 0])
            }
            predictor.propagate_in_video_preflight(state)
        objects = [
            Instance(
                key,
                self.targets[key].category,
                mask_box(mask),
                mask,
                self.targets[key].score,
            )
            for key, mask in masks.items()
            if key in self.targets and mask.any()
        ]
        if self.loader.accessed and max(self.loader.accessed) > t:
            raise RuntimeError("Future frame was encoded")
        if correction:
            audit.update(
                {
                    "after": sam_history_summary(state, correction.identity),
                    "correction_updates": sum(
                        key == correction.identity for key, _ in prompts
                    ),
                    "external_id": correction.identity,
                }
            )
            assert audit["correction_updates"] == 1
        self.frame = t
        return objects, {
            "frame": t,
            "actions": actions,
            "active_ids": list(self.targets),
            "output_ids": [o.identity for o in objects],
            "prompt_inputs": prompt_inputs,
            "intervention": audit,
        }
