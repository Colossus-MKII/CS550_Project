"""Output equality must include identity/metadata, not just mask appearance."""

from dataclasses import replace

import numpy as np

from tracking_lab.baseline_audit import equal_frame
from tracking_lab.common import Instance, mask_box


def test_frame_equality_checks_masks_identity_class_score_and_box():
    mask = np.zeros((8, 8), bool)
    mask[1:4, 1:4] = True
    original = Instance(1, "cat", mask_box(mask), mask, 0.9)
    assert equal_frame([original], [replace(original, mask=mask.copy())])
    assert not equal_frame([original], [])
    for field in (
        {"identity": 2},
        {"category": "dog"},
        {"score": 0.8},
        {"box": original.box + 1},
        {"mask": ~mask},
    ):
        assert not equal_frame([original], [replace(original, **field)])
