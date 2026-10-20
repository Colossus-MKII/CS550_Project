"""Correctness boundary for the reviewed SAM predictor's CPU-offloaded outputs.

The pinned upstream implementation queues a nonblocking GPU-to-CPU mask copy,
then its prompt API immediately consolidates those masks on CPU. Wait BEFORE
that host read, not merely after the public prompt API has already returned.
No model weights or installed upstream files are modified.
"""

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def synchronized_sam_offload(predictor):
    """Fence CUDA output copies; nested baseline/recovery callers fence once."""
    import torch

    original = predictor._run_single_frame_inference
    if getattr(original, "_cs550_synced_offload", False):
        yield
        return

    def synchronized(*args, **kwargs):
        result = original(*args, **kwargs)
        if torch.device(predictor.device).type == "cuda":
            torch.cuda.synchronize(predictor.device)
        return result

    synchronized._cs550_synced_offload = True
    with patch.object(predictor, "_run_single_frame_inference", synchronized):
        yield
