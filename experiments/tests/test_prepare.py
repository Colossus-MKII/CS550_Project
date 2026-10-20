"""Scientific data export fidelity, independent of the teaching website."""

import json
import re

import numpy as np
from PIL import Image
import pytest

from tracking_lab.prepare import export_sample


def fixture_sample(tmp_path):
    video = np.arange(2 * 3 * 4 * 3, dtype=np.uint8).reshape(2, 3, 4, 3)
    masks = np.zeros((2, 3, 4, 2), dtype=np.uint8)
    masks[0, 0, :2, 0] = 26
    masks[1, 1:, 1:, 1] = 9
    record = {
        "video_id": 2686,
        "shard": "example.tar",
        "tracks": [
            {"channel": 0, "category_id": 26, "category": "person", "areas": [2, 0]},
            {"channel": 1, "category_id": 9, "category": "dog", "areas": [0, 6]},
        ],
    }
    return video, masks, record


def test_preview_preserves_rgb_and_foreground_exactly(tmp_path):
    video, masks, record = fixture_sample(tmp_path)
    sample = export_sample(video, masks, record, tmp_path, "person")
    for t in range(2):
        np.testing.assert_array_equal(
            np.asarray(Image.open(tmp_path / f"2686/rgb/{t:05d}.png")), video[t]
        )
        for c in range(2):
            rgba = np.asarray(Image.open(tmp_path / f"2686/mask-{c}/{t:05d}.png"))
            np.testing.assert_array_equal(rgba[..., 3], (masks[t, ..., c] > 0) * 255)
            assert np.all(rgba[..., :3] == 255)
    assert sample["mask_shape"] == [2, 3, 4, 2]
    assert sample["channels"][1]["areas"] == [0, 6]


@pytest.mark.parametrize("fault", ["dimension", "category", "area", "audit", "rgb"])
def test_invalid_preview_rejected(tmp_path, fault):
    video, masks, record = fixture_sample(tmp_path)
    if fault == "dimension":
        masks = masks[:1]
    if fault == "category":
        masks[0, 0, 0, 0] = 99
    if fault == "area":
        record["tracks"][0]["areas"] = [1, 0]
    if fault == "audit":
        record["errors"] = ["bad annotation"]
    if fault == "rgb":
        video = video.astype(np.float32)
    with pytest.raises(ValueError):
        export_sample(video, masks, record, tmp_path, "person")
