"""Copy and audit inference HISTORY, never model weights.

SAM 2.1's reviewed predictor stores target history in five per-object containers.
R clears only that target's entries. Image features and positional constants are
image/model data, not target history, and remain available. IDs never change.
"""

import copy
from hashlib import sha256

import numpy as np
from .sam_io import synchronized_sam_offload  # compatibility for recovery callers

SAM_TARGET_KEYS = (
    "point_inputs_per_obj",
    "mask_inputs_per_obj",
    "output_dict_per_obj",
    "temp_output_dict_per_obj",
    "frames_tracked_per_obj",
)


def clone_tree(value):
    """Tensor-aware independent copy; no graph, weights, or shared mutable state."""
    import torch

    if isinstance(value, torch.Tensor):
        return value.detach().clone()
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, dict):
        return type(value)((key, clone_tree(item)) for key, item in value.items())
    if isinstance(value, list):
        return [clone_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(clone_tree(item) for item in value)
    return copy.deepcopy(value)


def state_digest(value):
    """Audit tensors/arrays by bytes, including BF16; ignore no numeric values."""
    import torch

    h = sha256()

    def visit(item):
        if isinstance(item, torch.Tensor):
            tensor = item.detach().cpu().contiguous()
            h.update(str((str(tensor.dtype), tuple(tensor.shape))).encode())
            h.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item, np.ndarray):
            h.update(str((str(item.dtype), item.shape)).encode())
            h.update(item.tobytes())
        elif isinstance(item, dict):
            for key in sorted(item, key=lambda key: (type(key).__name__, str(key))):
                visit(key)
                visit(item[key])
        elif isinstance(item, (list, tuple)):
            for part in item:
                visit(part)
        else:
            h.update(repr(item).encode())

    visit(value)
    return h.hexdigest()


def target_history(state, identity):
    index = state["obj_id_to_idx"][identity]
    return {key: state[key][index] for key in SAM_TARGET_KEYS}


def sam_history_summary(state, identity):
    history = target_history(state, identity)
    output = history["output_dict_per_obj"]
    return {
        "sha256": state_digest(history),
        "point_frames": sorted(history["point_inputs_per_obj"]),
        "mask_frames": sorted(history["mask_inputs_per_obj"]),
        "conditioning_frames": sorted(output["cond_frame_outputs"]),
        "nonconditioning_frames": sorted(output["non_cond_frame_outputs"]),
        "tracked_frames": sorted(history["frames_tracked_per_obj"]),
    }


def reset_sam_target(state, identity):
    """Clear old prompts, masks, memory features/pointers and tracked-frame flags.

    Direct per-object clearing avoids remove/re-add reindexing other objects.
    Fail on a different upstream state schema rather than silently partial-reset.
    """
    index = state["obj_id_to_idx"][identity]
    others = {
        key: state_digest(target_history(state, key))
        for key in state["obj_ids"]
        if key != identity
    }
    before = sam_history_summary(state, identity)
    for key in SAM_TARGET_KEYS:
        container = state[key][index]
        if key in {"output_dict_per_obj", "temp_output_dict_per_obj"}:
            if set(container) != {"cond_frame_outputs", "non_cond_frame_outputs"}:
                raise RuntimeError("Unreviewed SAM state schema")
            for outputs in container.values():
                outputs.clear()
        else:
            container.clear()
    assert others == {
        key: state_digest(target_history(state, key)) for key in others
    }, "Reset modified another object's history"
    return {
        "before": before,
        "after_clear": sam_history_summary(state, identity),
        "other_targets_unchanged": True,
        "external_id_unchanged": identity,
    }
