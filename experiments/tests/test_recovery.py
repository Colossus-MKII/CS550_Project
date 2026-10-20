"""Small analytic tests BEFORE spending GPU time on the controlled pilot."""

import json
import copy
import numpy as np
import pytest

from tracking_lab import PACKAGE_ROOT, ROOT
from tracking_lab.common import Instance, mask_box, load_predictions
from tracking_lab.recovery_engines import ByteEngine, Correction
from tracking_lab.recovery_metrics import evaluate_recovery
from tracking_lab.recovery_events import anchor_identity
from tracking_lab.recovery_state import (
    clone_tree,
    target_history,
    state_digest,
    reset_sam_target,
    SAM_TARGET_KEYS,
    synchronized_sam_offload,
)


def test_offload_fence_precedes_host_read_and_restores_upstream_method():
    from types import SimpleNamespace
    from unittest.mock import patch

    calls = []

    def original(value):
        calls.append("copy_queued")
        return value

    predictor = SimpleNamespace(device="cuda:0", _run_single_frame_inference=original)
    with patch(
        "torch.cuda.synchronize",
        side_effect=lambda device: calls.append("copy_complete"),
    ):
        with synchronized_sam_offload(predictor):
            assert predictor._run_single_frame_inference(7) == 7
            calls.append("cpu_read")
    assert calls == ["copy_queued", "copy_complete", "cpu_read"]
    assert predictor._run_single_frame_inference is original


def test_nested_offload_guard_fences_once_and_restores_after_exception():
    from types import SimpleNamespace
    from unittest.mock import patch

    original = lambda: 7
    predictor = SimpleNamespace(device="cuda:0", _run_single_frame_inference=original)
    with patch("torch.cuda.synchronize") as fence:
        with pytest.raises(ValueError):
            with synchronized_sam_offload(predictor):
                with synchronized_sam_offload(predictor):
                    assert predictor._run_single_frame_inference() == 7
                    raise ValueError("test")
        fence.assert_called_once_with("cuda:0")
    assert predictor._run_single_frame_inference is original


def test_output_provenance_uses_exact_detector_values_not_track_id():
    from dataclasses import replace
    from tracking_lab.recovery_report import source_detection_indices

    detection = obj(9)
    output = replace(detection, identity=1)
    assert source_detection_indices(output, [detection]) == [9]
    assert source_detection_indices(output, [replace(detection, score=0.8)]) == []
    assert source_detection_indices(
        output, [detection, replace(detection, identity=10)]
    ) == [9, 10]


from tracking_lab.bytetrack import run_bytetrack
from tracking_lab.recovery import assert_same_predictions

CONFIG = json.loads((PACKAGE_ROOT / "defaults/stage1.json").read_text())


def obj(identity=1, x=4):
    mask = np.zeros((24, 30), bool)
    mask[3:14, x : x + 6] = True
    return Instance(identity, "person", mask_box(mask), mask, 0.9)


def test_byte_adapter_exact_native_replay_and_branch_independence():
    observations = [[obj(0, x=4 + t)] for t in range(5)] + [[], [obj(0, x=10)]]
    expected, _ = run_bytetrack(observations, (24, 30), CONFIG)
    engine = ByteEngine(CONFIG)
    for t, detection in enumerate(observations):
        actual, _ = engine.step(t, detection)
        assert_same_predictions(expected[t], actual)
    old = engine.snapshot(engine.find(1)[1])
    h, r = engine.fork(), engine.fork()
    box = np.array([17, 3, 23, 14], np.float32)
    h.step(7, [obj(0, 17)], Correction(1, "person", box, 0.9, 0, False))
    _, trace = r.step(7, [obj(0, 17)], Correction(1, "person", box, 0.9, 0, True))
    hs, rs = h.find(1)[1], r.find(1)[1]
    assert not np.array_equal(hs.mean, rs.mean)
    assert rs.mean[4:].tolist() == [0, 0, 0, 0]
    assert trace["intervention"]["correction_updates"] == 1
    assert hs.track_id == rs.track_id
    assert hs.frame_id == rs.frame_id and hs.start_frame == rs.start_frame
    assert hs.is_activated == rs.is_activated == True
    assert hs.tracklet_len == rs.tracklet_len
    assert engine.snapshot(engine.find(1)[1]) == old


def test_byte_correction_does_not_reset_other_target_or_emit_gt_mask():
    e = ByteEngine(CONFIG)
    e.step(0, [obj(0, 2), obj(1, 20)])
    h, r = e.fork(), e.fork()
    outcomes = []
    for branch, reset in ((h, False), (r, True)):
        predictions, _ = branch.step(
            1,
            [obj(0, 3), obj(1, 20)],
            Correction(1, "person", obj().box, 1.0, 0, reset),
        )
        assert [x.identity for x in predictions] == [2]
        outcomes.append(branch.snapshot(branch.find(2)[1]))
    assert outcomes[0] == outcomes[1]
    with pytest.raises(ValueError):
        e.find(999)


def fake_sam_state():
    import torch

    state = {"obj_id_to_idx": {7: 0, 8: 1}, "obj_ids": [7, 8]}
    for key in SAM_TARGET_KEYS:
        if key in {"output_dict_per_obj", "temp_output_dict_per_obj"}:
            state[key] = {
                i: {
                    "cond_frame_outputs": {
                        0: {"memory": torch.ones(2, dtype=torch.bfloat16)}
                    },
                    "non_cond_frame_outputs": {1: {"pointer": torch.ones(2)}},
                }
                for i in (0, 1)
            }
        else:
            state[key] = {0: {0: torch.ones(2)}, 1: {0: torch.zeros(2)}}
    return state


def test_sam_reset_clears_all_target_history_without_id_or_other_changes():
    original = fake_sam_state()
    h, r = clone_tree(original), clone_tree(original)
    initial = state_digest(original)
    audit = reset_sam_target(r, 7)
    assert state_digest(original) == state_digest(h) == initial
    assert r["obj_id_to_idx"] == original["obj_id_to_idx"] and r["obj_ids"] == [7, 8]
    assert state_digest(target_history(r, 8)) == state_digest(target_history(h, 8))
    assert audit["other_targets_unchanged"]
    for value in target_history(r, 7).values():
        assert value == {} or value == {
            "cond_frame_outputs": {},
            "non_cond_frame_outputs": {},
        }


def score(pred, gt=None, **kwargs):
    gt = [[obj()]] * len(pred) if gt is None else gt
    return evaluate_recovery(gt, pred, 7, 1, 0, len(gt) - 1, **kwargs)


def test_perfect_recovery_excludes_correction_and_reports_confirmation():
    result = score([[], [obj(7)], [obj(7)], [obj(7)], [obj(7)]])
    assert result["summary"]["recovery_onset_offset"] == 1
    assert result["summary"]["recovery_confirmed_offset"] == 3
    assert result["summary"]["correct_visible_fraction"] == 1
    assert len(result["curve"]) == 4


def test_new_id_or_wrong_object_is_not_recovery():
    for pred in ([[obj(8)]] * 5, [[obj(7, 20)]] * 5, [[]] * 5):
        result = score(pred)
        assert result["summary"]["recovered"] is False
        assert result["summary"]["mean_visible_mask_iou"] == 0
        assert result["summary"]["recovery_confirmed_offset"] is None


def test_relapse_and_invisibility_are_not_deleted_from_analysis():
    pred = [[obj(7)]] * 7 + [[]]
    gt = [[obj()]] * 7 + [[obj()]]
    gt[4] = []
    result = score(pred, gt)
    assert result["summary"]["recovered"]
    assert result["summary"]["invisible_false_outputs"] == 1
    assert result["summary"]["visible_steps"] == 6
    assert result["curve"][3]["success_streak"] == 0
    assert result["summary"]["relapses"] == 1


def test_anchor_uses_first_qualified_prefix_track_not_best_future_track():
    gt = [[obj()]] * 4
    pred = [[obj(7)], [obj(8)], [obj(8)], [obj(9)]]
    anchor = anchor_identity(gt, pred, 1, "person", 3, 0.5)
    assert anchor["prediction_id"] == 7 and anchor["anchor_frame"] == 0
    assert anchor_identity(gt, [[]] * 4, 1, "person", 3, 0.5) is None


def test_duplicate_fixed_id_and_short_window_fail():
    with pytest.raises(ValueError):
        score([[obj(7), obj(7)]] * 5)
    with pytest.raises(ValueError):
        evaluate_recovery([[obj()]] * 3, [[obj(7)]] * 3, 7, 1, 1, 8)


def test_byte_assignment_probe_does_not_change_native_output():
    from ultralytics.trackers.utils import matching

    original = (matching.iou_distance, matching.linear_assignment)
    plain, logged = ByteEngine(CONFIG), ByteEngine(CONFIG, association_diagnostics=True)
    for t in range(8):
        detections = [obj(31, 4 + t), obj(72, 20)] if t != 5 else []
        expected, _ = plain.step(t, detections)
        actual, trace = logged.step(t, detections)
        assert_same_predictions(expected, actual)
        person = next(a for a in trace["assignments"] if a["category"] == "person")
        assert [a["stage"] for a in person["stages"]] == [
            "high_confidence",
            "low_confidence",
            "unconfirmed",
        ]
        for stage in person["stages"]:
            assert stage["shape"] == [len(stage["tracks"]), len(stage["detections"])]
            assert all(d["detector_index"] in {31, 72} for d in stage["detections"])
    assert original == (matching.iou_distance, matching.linear_assignment)


def test_assignment_probe_restores_modules_on_exception():
    from ultralytics.trackers.utils import matching
    from tracking_lab.association_trace import observe_assignments

    original = (matching.iou_distance, matching.linear_assignment)
    with pytest.raises(ValueError):
        with observe_assignments("person", [], {}):
            raise ValueError("simulated tracker failure")
    assert original == (matching.iou_distance, matching.linear_assignment)


@pytest.mark.parametrize("with_detection", [False, True])
def test_sam_skip_is_target_only_and_does_not_refresh_lifetime(
    monkeypatch, with_detection
):
    from types import SimpleNamespace
    import torch
    from tracking_lab import recovery_engines as module
    from tracking_lab.sam_baseline import Target

    calls = []
    mask = obj().mask

    def prompt(state, frame_idx, obj_id, box):
        calls.append(obj_id)
        return frame_idx, [1, 2], torch.ones((2, 1, *mask.shape))

    engine = object.__new__(module.SamEngine)
    engine.predictor = SimpleNamespace(
        add_all_frames_to_correct_as_cond=True,
        add_new_points_or_box=prompt,
        propagate_in_video_preflight=lambda state: None,
    )
    engine.config, engine.state = CONFIG, {}
    engine.loader = SimpleNamespace(accessed=[])
    engine.targets = {
        i: Target(i, "person", obj(x=x).box, 4, 0.9) for i, x in [(1, 4), (2, 20)]
    }
    engine.next_id, engine.frame, engine.skip_refresh = 3, 4, (1, 5)
    monkeypatch.setattr(
        module, "propagate_one", lambda *args: {1: obj(x=4).mask, 2: obj(x=20).mask}
    )
    detections = [obj(7, 20)] + ([obj(9, 4)] if with_detection else [])
    _, trace = engine.step(5, detections)
    assert calls == [2]  # Other target still consumes its ordinary prompt.
    assert trace["prompt_inputs"] == [
        {
            "id": 2,
            "source": "native_refresh",
            "box_xyxy": detections[0].box.tolist(),
            "score": detections[0].score,
            "detector_index": detections[0].identity,
        }
    ]
    assert engine.targets[1].last_detection == 4
    assert engine.targets[2].last_detection == 5
    assert {"action": "skip_refresh_slot", "id": 1} in trace["actions"]
    assert sum(a["action"] == "skipped_refresh" for a in trace["actions"]) == int(
        with_detection
    )
