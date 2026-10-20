"""Boundary cases for interpreting exported masks and paired NPY features."""

from io import BytesIO
import tarfile
import zipfile

import numpy as np

from tracking_lab.audit import inspect_masks, inspect_shard, read_header, summarize


CATEGORIES = {5: "car", 6: "cat", 9: "dog", 19: "horse", 26: "person"}


def test_channel_ids_and_gaps_preserve_instance_identity():
    masks = np.zeros((3, 2, 2, 2), dtype=np.uint8)
    masks[0, 0, 0, 0] = masks[2, 1, 1, 0] = 26
    masks[1, 0, 0, 1] = 9
    tracks, errors, warnings, empty = inspect_masks(masks, CATEGORIES)
    assert not errors and not warnings and not empty
    assert tracks[0]["category"] == "person"
    assert tracks[0]["visible_frames"] == [0, 2]
    assert tracks[0]["max_visibility_gap_in_exported_steps"] == 1
    assert tracks[1]["category"] == "dog"


def test_mixed_categories_are_not_silently_counted_as_one_track():
    masks = np.zeros((2, 2, 2, 1), dtype=np.uint8)
    masks[0, 0, 0, 0] = 26
    masks[1, 0, 0, 0] = 9
    _, errors, _, _ = inspect_masks(masks, CATEGORIES)
    assert any("multiple categories" in error for error in errors)


def test_empty_and_unknown_channels_are_reported():
    masks = np.zeros((2, 2, 2, 2), dtype=np.uint8)
    masks[0, 0, 0, 1] = 99
    tracks, errors, warnings, _ = inspect_masks(masks, CATEGORIES)
    assert not tracks
    assert len(errors) == len(warnings) == 1


def test_object_array_header_is_rejected_without_unpickling():
    data = BytesIO()
    np.save(data, np.array([{"example": 1}], dtype=object))
    data.seek(0)
    try:
        read_header(data, len(data.getvalue()))
    except ValueError as error:
        assert "pickled" in str(error)
    else:
        raise AssertionError("Object data must be rejected")


def make_archive(path, mismatch=False):
    inner_bytes = BytesIO()
    with tarfile.open(fileobj=inner_bytes, mode="w") as inner:
        video = np.zeros((3, 2, 2, 3), dtype=np.uint8)
        masks = np.zeros((2 if mismatch else 3, 2, 2, 2), dtype=np.uint8)
        masks[..., 0] = 26
        masks[..., 1] = 9
        for name, array in [("42.video.npy", video), ("42.segmentations.npy", masks)]:
            data = BytesIO()
            np.save(data, array, allow_pickle=False)
            info = tarfile.TarInfo(name)
            info.size = len(data.getvalue())
            data.seek(0)
            inner.addfile(info, data)
    name = "ytvis2021_resized/ytvis-validation-000000.tar"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as outer:
        outer.writestr(name, inner_bytes.getvalue())
    return name


def test_nested_archive_counts_unique_videos_not_category_sum(tmp_path):
    archive = tmp_path / "example.zip"
    name = make_archive(archive)
    shard = inspect_shard(archive, name, CATEGORIES)
    result = summarize([shard])
    assert shard["zip_crc_verified"]
    assert result["target_counts"]["person"]["videos"] == 1
    assert result["target_counts"]["dog"]["videos"] == 1
    assert result["target_union_video_count"] == 1
    assert not result["supports_requested_200_target_videos"]
    assert not result["errors"]


def test_misaligned_frames_are_excluded_from_usable_counts(tmp_path):
    archive = tmp_path / "mismatch.zip"
    name = make_archive(archive, mismatch=True)
    result = summarize([inspect_shard(archive, name, CATEGORIES)])
    assert result["annotated_video_count"] == 1
    assert result["structurally_valid_annotated_video_count"] == 0
    assert result["target_union_video_count"] == 0
    assert result["error_video_count"] == 1
