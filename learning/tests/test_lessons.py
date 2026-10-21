import cv2
import numpy as np
import pytest

from learning.common import VideoWriter, fit_size, label_frame, mask_iou, prepare_clip, validate_box
from learning.report import write_report
from learning.yolo_lessons import select_prompts


def test_resize_even_and_bounded():
    assert fit_size(1920, 1080, 640) == (640, 360)
    assert fit_size(321, 241, 640) == (320, 240)


def test_caption_does_not_cover_pixels():
    frame = np.full((60, 80, 3), 123, np.uint8)
    result = label_frame(frame, "Test", 0)
    assert result.shape == (108, 80, 3)
    assert np.array_equal(result[48:], frame)


def test_box_and_bad_inputs():
    assert validate_box([0, 0, 80, 40], 80, 40) == [0, 0, 80, 40]
    for box in ([80, 0, 0, 40], [-1, 0, 80, 40], [0, 0, 81, 40], [0, 0, float("nan"), 40]):
        with pytest.raises(ValueError):
            validate_box(box, 80, 40)


def test_mask_iou_and_empty_masks():
    assert mask_iou([1, 1, 0], [1, 0, 1]) == pytest.approx(1 / 3)
    assert mask_iou([0, 0], [0, 0]) is None
    assert mask_iou([0, 0], [1, 0]) == 0
    with pytest.raises(ValueError):
        mask_iou([0], [0, 1])


def test_prompts_only_take_top_scores_and_do_not_mutate():
    detections = [{"confidence": score, "class_name": "dog", "box_xyxy": [1, 2, 8, 9]} for score in [0.2, 0.9, 0.8]]
    result = select_prompts(detections, 2)
    assert [p["confidence"] for p in result] == [0.9, 0.8]
    assert [p["object_id"] for p in result] == [1, 2]
    assert all(p["frame"] == 0 for p in result)
    assert detections[0]["confidence"] == 0.2
    assert select_prompts([], 2) == []


def test_video_round_trip_and_clip_start(tmp_path):
    source = tmp_path / "tiny.mp4"
    with VideoWriter(source, (80, 60), 12) as writer:
        for gray in [0, 60, 120, 180, 240]:
            writer.write(np.full((60, 80, 3), gray, np.uint8))
    run = tmp_path / "run"
    run.mkdir()
    paths, clip = prepare_clip(source, run, 2, 640, 2)
    assert len(paths) == clip["frames"] == 2
    assert clip["fps"] == 12
    assert clip["size"] == [80, 60]
    assert cv2.imread(str(paths[0])).mean() == pytest.approx(120, abs=4)


def test_empty_input(tmp_path):
    with pytest.raises(ValueError, match="Cannot open"):
        prepare_clip(tmp_path / "missing.mp4", tmp_path, 2, 640, 0)


def test_report_escapes_paths_and_failure(tmp_path):
    write_report(tmp_path, {"status": "failed", "source": "<script>bad</script>", "error": "test failure"})
    html = (tmp_path / "handbook.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;bad&lt;/script&gt;" in html
    assert "<script>bad</script>" not in html
    assert "test failure" in html
    assert "@@" not in html
    assert "仅供背景阅读，不在最新版项目范围内" in html
