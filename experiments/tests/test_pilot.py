"""CPU analytic tests for model-independent contracts and online orchestration."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest

from tracking_lab import PACKAGE_ROOT
from tracking_lab.common import (
    Instance,
    associate,
    box_iou,
    load_predictions,
    mask_box,
    mask_iou,
    save_predictions,
)
from tracking_lab.bytetrack import run_bytetrack
from tracking_lab.dataset import VideoInput
from tracking_lab.diagnose import diagnose
from tracking_lab.evaluate import evaluate_all, self_checks, similarity_data
from tracking_lab.sam_baseline import PNGFrames, run_sam

CONFIG = json.loads((PACKAGE_ROOT / "defaults/stage1.json").read_text(encoding="utf-8"))


def obj(identity=1, category="person", x=2, score=0.9):
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:8, x : x + 4] = True
    return Instance(identity, category, mask_box(mask), mask, score)


def test_exclusive_boxes_and_empty_masks():
    mask = np.zeros((4, 5), dtype=bool)
    mask[1, 2] = True
    assert mask_box(mask).tolist() == [2, 1, 3, 2]
    assert box_iou(mask_box(mask), mask_box(mask)) == 1
    assert mask_iou(mask, mask) == 1
    assert mask_iou(np.zeros_like(mask), np.zeros_like(mask)) == 0


def test_gated_assignment_maximizes_valid_pair_count():
    tracks = [obj(1), obj(2)]
    with patch("tracking_lab.common.box_iou", side_effect=[0.9, 0.51, 0.5, 0.49]):
        pairs, _, _ = associate(tracks, tracks, 0.5)
    assert set(pairs) == {(0, 1), (1, 0)}


def test_class_gate_cannot_swap_people_and_dogs():
    pairs, unmatched_t, unmatched_d = associate(
        [obj(category="person")], [obj(category="dog")], 0.3
    )
    assert pairs == [] and unmatched_t == [0] and unmatched_d == [0]


def test_prediction_round_trip_and_empty_frame(tmp_path):
    expected = [[obj(), obj(2, "dog", 9)], [], [obj(3)]]
    save_predictions(tmp_path, expected, (20, 20))
    actual = load_predictions(tmp_path)
    assert [len(frame) for frame in actual] == [2, 0, 1]
    np.testing.assert_array_equal(actual[0][1].mask, expected[0][1].mask)
    assert actual[0][1].identity == 2 and actual[0][1].category == "dog"


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_predictions(tmp_path, [[obj(1), obj(1)]], (20, 20))


def test_bytetrack_mask_uses_detection_index_not_output_order():
    # The first detection is low-confidence; only the second may start a track.
    observations = [[obj(0, x=2, score=0.15), obj(1, x=11, score=0.95)]]
    frames, _ = run_bytetrack(observations, (20, 20), CONFIG)
    assert len(frames[0]) == 1
    np.testing.assert_array_equal(frames[0][0].mask, observations[0][1].mask)


def test_bytetrack_low_confidence_second_stage_keeps_original_mask():
    observations = [
        [obj(0, x=11, score=0.95)],
        [obj(0, x=2, score=0.95), obj(1, x=11, score=0.15)],
    ]
    frames, _ = run_bytetrack(observations, (20, 20), CONFIG)
    old_id = frames[0][0].identity
    continued = next(o for o in frames[1] if o.identity == old_id)
    assert continued.score == 0.15
    np.testing.assert_array_equal(continued.mask, observations[1][1].mask)


def test_bytetrack_categories_have_unique_ids_and_empty_steps_advance():
    observations = [[obj(0), obj(1, "dog", 10)], [], [obj(0), obj(1, "dog", 10)]]
    frames, trace = run_bytetrack(observations, (20, 20), CONFIG)
    ids = {o.category: o.identity for o in frames[0]}
    assert len(set(ids.values())) == 2
    assert not frames[1]
    assert {o.category: o.identity for o in frames[2]} == ids
    assert all(o["state"] == 2 for o in trace[1]["states"])


def test_evaluator_analytic_cases():
    assert all(case["passed"] for case in self_checks().values())


def test_class_macro_does_not_overweight_frequent_people():
    gt = [[obj(1, "person")]] * 9 + [[obj(2, "dog")]]
    pred = [[obj(7, "person")]] * 9 + [[]]
    scores = evaluate_all({"video": (gt, pred)})
    assert scores["macro"]["HOTA"] == pytest.approx(0.5)
    assert scores["macro"]["IDF1"] == pytest.approx(0.5)
    assert scores["macro"]["FN"] == 1


def test_frame_mismatch_fails_not_silent_truncation():
    with pytest.raises(ValueError):
        similarity_data([[obj()]], [], "person")


def test_duplicate_prediction_is_false_positive():
    scores = evaluate_all({"video": ([[obj()]], [[obj(8), obj(9)]])})
    assert scores["macro"]["FP"] == 1 and scores["macro"]["IDF1"] == pytest.approx(
        2 / 3
    )


def test_diagnostics_distinguish_localization_and_identity():
    gt = [[obj()], [obj()]]
    pred = [[obj(7)], [obj(8)]]
    frames, summary = diagnose(gt, pred, gt)
    assert summary["mean_best_same_class_mask_iou_visible_gt"] == 1
    assert frames[1]["targets"][0]["diagnostic_id_change"]
    assert summary["diagnostic_id_changes"] == 1


def test_missing_prediction_is_zero_iou_and_adequate_detection_flag():
    frames, summary = diagnose([[obj()]], [[]], [[obj()]])
    assert summary["mean_best_same_class_mask_iou_visible_gt"] == 0
    assert frames[0]["targets"][0]["reason"] == "good_yolo_mask_but_no_matching_output"


def test_png_adapter_matches_upstream_normalization_and_is_lazy(tmp_path):
    import torch
    from sam2.utils.misc import _load_img_as_tensor

    paths = []
    for t in range(3):
        path = tmp_path / f"{t:05d}.png"
        Image.fromarray(np.full((12, 16, 3), 30 + t, dtype=np.uint8)).save(path)
        paths.append(path)
    loader = PNGFrames(paths, 32)
    assert not loader.accessed and len(loader) == 3
    actual = loader[0]
    original, _, _ = _load_img_as_tensor(str(paths[0]), 32)
    expected = (
        original.float() - torch.tensor([0.485, 0.456, 0.406])[:, None, None]
    ) / torch.tensor([0.229, 0.224, 0.225])[:, None, None]
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert loader.accessed == [0]


class FakeSAM:
    image_size = 32
    add_all_frames_to_correct_as_cond = True
    device = "cpu"

    def _run_single_frame_inference(self, *args, **kwargs):
        raise AssertionError("The orchestration fake does not execute neural inference")

    def __init__(self):
        self.commits = 0

    def init_state(self, *args, **kwargs):
        return {"obj_ids": [], "boxes": {}}

    def output(self, state, t):
        import torch

        masks = []
        for key in state["obj_ids"]:
            mask = np.full((1, 20, 20), -1, dtype=np.float32)
            x, y, x2, y2 = state["boxes"][key].astype(int)
            mask[:, y:y2, x:x2] = 1
            masks.append(mask)
        return t, list(state["obj_ids"]), torch.from_numpy(np.stack(masks))

    def propagate_in_video(
        self, state, start_frame_idx, max_frame_num_to_track, reverse
    ):
        assert max_frame_num_to_track == 0 and not reverse
        yield self.output(state, start_frame_idx)

    def add_new_points_or_box(self, state, frame_idx, obj_id, box):
        if obj_id not in state["obj_ids"]:
            state["obj_ids"].append(obj_id)
        state["boxes"][obj_id] = box
        return self.output(state, frame_idx)

    def propagate_in_video_preflight(self, state):
        self.commits += 1

    def remove_object(self, state, key, **kwargs):
        state["obj_ids"].remove(key)
        del state["boxes"][key]


def test_sam_late_discovery_refresh_and_retirement_use_only_yolo(tmp_path):
    fake = FakeSAM()
    video = VideoInput(1, tuple(tmp_path / f"{i}.png" for i in range(7)), 20, 20)
    observations = [[], [], [obj(0, "dog", 10)], [], [], [], []]
    config = {**CONFIG, "discovery_interval": 2, "sam_retention_steps": 3}
    frames, events, stats = run_sam(fake, video, observations, config)
    assert not frames[0] and not frames[1]
    assert len(frames[2]) == 1 and frames[2][0].category == "dog"
    assert not frames[6] and events[6]["actions"][0]["action"] == "retire"
    assert [e["frame"] for e in events if e["detector_called"]] == [0, 2, 4, 6]
    assert stats["detector_calls_used"] == 4 and fake.commits == 1


def test_sam_matched_refresh_keeps_external_id(tmp_path):
    fake = FakeSAM()
    video = VideoInput(1, tuple(tmp_path / f"{i}.png" for i in range(3)), 20, 20)
    observations = [[obj(0)], [obj(0)], [obj(0)]]
    config = {**CONFIG, "discovery_interval": 2}
    frames, events, _ = run_sam(fake, video, observations, config)
    assert [f[0].identity for f in frames] == [1, 1, 1]
    assert events[2]["actions"][0]["action"] == "refresh"
    assert fake.commits == 2
