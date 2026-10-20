"""Cheap checks of the long-window report before looking at GPU outcomes."""

import json
from dataclasses import replace

import numpy as np

from tracking_lab import PACKAGE_ROOT
from tracking_lab.common import Instance, mask_box
from tracking_lab.recovery_long_report import checkpoint_score, different_frames


def item(identity):
    mask = np.zeros((10, 12), bool)
    mask[2:8, 3:9] = True
    return Instance(identity, "cat", mask_box(mask), mask, 0.9)


def test_frozen_configs_differ_only_in_diagnostic_switch_and_description():
    normal, skipped = [
        json.loads((PACKAGE_ROOT / "defaults" / name).read_text())
        for name in ("recovery_long_normal.json", "recovery_long_skip.json")
    ]
    assert normal.pop("sam_skip_next_refresh") is False
    assert skipped.pop("sam_skip_next_refresh") is True
    normal.pop("role")
    skipped.pop("role")
    assert normal == skipped
    assert normal["report_windows"] == [8, 20, 30]
    assert normal["window"] == 30


def test_checkpoints_share_one_long_prediction_and_exclude_correction():
    truth = [[item(2)]] * 32
    pred = [[]] * 2 + [[item(7)]] * 15 + [[]] * 15
    event, record = {"frame": 1, "gt_id": 2}, {"prediction_id": 7}
    config = {"mask_iou_threshold": 0.5, "streak_required": 3}
    short = checkpoint_score(truth, pred, None, event, record, 8, config)
    long = checkpoint_score(truth, pred, None, event, record, 30, config)
    assert short["summary"]["correct_visible_steps"] == 8
    assert long["summary"]["correct_visible_steps"] == 15
    assert long["summary"]["relapses"] == 1
    assert long["curve"][:8] == short["curve"]


def test_exact_differences_distinguish_target_from_other_object():
    a = [[item(7), item(8)]]
    b = [[item(7), replace(item(8), score=0.8)]]
    assert different_frames(a, b) == [0]
    assert different_frames(a, b, identity=7) == []
