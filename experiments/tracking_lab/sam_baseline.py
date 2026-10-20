"""B0: forward-only detector-assisted SAM 2.1, never given GT or ByteTrack IDs.

For each exported frame:
1. Retire targets whose last accepted YOLO observation exceeds the lifetime.
2. Propagate all remaining targets to this frame, using past inference history.
3. At scheduled discovery frames, match YOLO boxes to same-class propagated
   mask boxes. Refresh matched IDs, discover unmatched boxes, suppress duplicates.
4. Commit current box prompts to SAM memory; never rerun an earlier scored frame.

All lifecycle units are EXPORTED STEPS. These are not original-video seconds.
"""

from dataclasses import dataclass
from unittest.mock import patch

import numpy as np

from .common import Instance, associate, box_iou, mask_box
from .sam_io import synchronized_sam_offload


class PNGFrames:
    """Lazy source-PNG loader with upstream SAM resize/normalization, CPU-only.

    Official init_state only exposes JPEG folders/MP4. A narrowly scoped loader
    adapter lets its UNMODIFIED state initializer consume lossless source PNGs.
    No JPEG recoding, changed encoder resolution, or future-frame encoding.
    """

    def __init__(self, paths, image_size):
        import torch

        self.paths = paths
        self.image_size = image_size
        self.accessed = []
        self.mean = torch.tensor((0.485, 0.456, 0.406), dtype=torch.float32)[
            :, None, None
        ]
        self.std = torch.tensor((0.229, 0.224, 0.225), dtype=torch.float32)[
            :, None, None
        ]

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        from sam2.utils.misc import _load_img_as_tensor

        self.accessed.append(index)
        image, _, _ = _load_img_as_tensor(str(self.paths[index]), self.image_size)
        return (image.float() - self.mean) / self.std


@dataclass
class Target:
    identity: int
    category: str
    box: np.ndarray
    last_detection: int
    score: float


def init_png_state(predictor, video):
    loader = PNGFrames(video.rgb_paths, predictor.image_size)
    # No site-packages files are edited. Restore the upstream loader immediately.
    # The runner is single-threaded; do not initialize predictors concurrently.
    with patch(
        "sam2.sam2_video_predictor.load_video_frames",
        return_value=(loader, video.height, video.width),
    ):
        state = predictor.init_state(
            str(video.rgb_paths[0].parent),
            offload_video_to_cpu=True,
            offload_state_to_cpu=True,
        )
    return state, loader


def propagate_one(predictor, state, t):
    if not state["obj_ids"]:
        return {}
    generator = predictor.propagate_in_video(
        state, start_frame_idx=t, max_frame_num_to_track=0, reverse=False
    )
    try:
        index, ids, logits = next(generator)
        if index != t:
            raise RuntimeError("SAM returned an unexpected frame")
        return {
            int(key): mask for key, mask in zip(ids, (logits > 0).cpu().numpy()[:, 0])
        }
    finally:
        generator.close()


def run_sam(predictor, video, detections, config):
    """Normal B0 entry point: safe for CPU-offloaded prompt masks by default."""
    with synchronized_sam_offload(predictor):
        return _run_sam(predictor, video, detections, config)


def _run_sam(predictor, video, detections, config):
    state, loader = init_png_state(predictor, video)
    targets = {}
    next_id = 1
    frames = []
    events = []
    for t in range(len(video.rgb_paths)):
        actions = []
        for key, target in list(targets.items()):
            if t - target.last_detection > config["sam_retention_steps"]:
                predictor.remove_object(state, key, strict=True, need_output=False)
                del targets[key]
                actions.append({"action": "retire", "id": key})
        masks = propagate_one(predictor, state, t)
        # Update association boxes using ONLY current SAM outputs. Empty outputs
        # keep the last box during retention, never a box derived from annotations.
        for key, mask in masks.items():
            if mask.any():
                targets[key].box = mask_box(mask)
        if t % config["discovery_interval"] == 0:
            observations = [
                o for o in detections[t] if o.score >= config["sam_prompt_conf"]
            ]
            current = list(targets.values())
            matches, _, unmatched = associate(
                current, observations, config["sam_match_iou"]
            )
            prompts = []
            for ti, di in matches:
                target, det = current[ti], observations[di]
                target.box = det.box.copy()
                target.last_detection = t
                target.score = det.score
                prompts.append((target.identity, det))
                actions.append(
                    {
                        "action": "refresh",
                        "id": target.identity,
                        "detector_index": det.identity,
                    }
                )
            for di in unmatched:
                det = observations[di]
                if any(
                    target.category == det.category
                    and box_iou(target.box, det.box) >= config["sam_duplicate_iou"]
                    for target in targets.values()
                ):
                    actions.append(
                        {"action": "suppress_duplicate", "detector_index": det.identity}
                    )
                    continue
                if len(targets) >= 32:
                    raise RuntimeError(
                        "Pilot target budget exceeded; fail rather than silently truncate"
                    )
                key = next_id
                next_id += 1
                targets[key] = Target(key, det.category, det.box.copy(), t, det.score)
                prompts.append((key, det))
                actions.append(
                    {"action": "discover", "id": key, "detector_index": det.identity}
                )
            if prompts:
                # Corrected frames are explicitly conditioning frames. Without
                # this flag, a second generic propagation can overwrite a refresh.
                if not predictor.add_all_frames_to_correct_as_cond:
                    raise RuntimeError("SAM conditioning configuration changed")
                for key, det in prompts:
                    index, ids, logits = predictor.add_new_points_or_box(
                        state, frame_idx=t, obj_id=key, box=det.box.astype(np.float32)
                    )
                masks = {
                    int(key): mask
                    for key, mask in zip(ids, (logits > 0).cpu().numpy()[:, 0])
                }
                # Encode current prompted outputs into memory for FUTURE frames.
                predictor.propagate_in_video_preflight(state)
        objects = []
        for key, mask in masks.items():
            if key in targets and mask.any():
                target = targets[key]
                objects.append(
                    Instance(key, target.category, mask_box(mask), mask, target.score)
                )
        frames.append(objects)
        if loader.accessed and max(loader.accessed) > t:
            raise RuntimeError("Future frame was encoded")
        events.append(
            {
                "frame": t,
                "detector_called": t % config["discovery_interval"] == 0,
                "actions": actions,
                "active_ids": list(targets),
                "output_ids": [o.identity for o in objects],
            }
        )
        if t % 10 == 0:
            print(
                f"SAM {video.video_id}: {t+1}/{len(video.rgb_paths)}, {len(targets)} active",
                flush=True,
            )
    # Keep a checkable frame-access trace. Model weights and other videos untouched.
    return (
        frames,
        events,
        {
            "frame_accesses": loader.accessed,
            "detector_calls_used": sum(e["detector_called"] for e in events),
            "source_frames": len(video.rgb_paths),
            "precision": "bfloat16 autocast",
            "offload_video_to_cpu": True,
            "offload_state_to_cpu": True,
            "cpu_offload_guard": "CUDA fence before CPU prompt-mask consolidation",
            "add_all_frames_to_correct_as_cond": True,
            "fill_hole_area": 0,
            "input_adapter": "upstream image loader/normalization, lossless PNG via scoped init_state loader adapter",
        },
    )
