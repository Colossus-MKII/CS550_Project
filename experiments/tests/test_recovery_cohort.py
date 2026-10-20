"""Cohort routing and read-only diagnosis tests; never spend GPU time here."""

import json
from pathlib import Path

import numpy as np
import pytest

from tracking_lab.common import Instance, mask_box
from tracking_lab.recovery_cohort import prepare_plan
from tracking_lab.recovery_cohort_report import (
    lifecycle_state,
    audit_prompts,
    aggregate,
    different_KF_state_steps,
    prompt_api_schedule,
)


def observation():
    mask = np.zeros((12, 12), bool)
    mask[2:8, 3:9] = True
    return Instance(5, "person", mask_box(mask), mask, 0.9)


def test_existing_cohort_output_is_never_replaced(tmp_path):
    with pytest.raises(FileExistsError):
        prepare_plan("not-read.json", "unused", "unused", tmp_path)


def test_boundary_2967_is_rejected_before_any_baseline_or_model(tmp_path):
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "events": [
                    {"event_id": f"E{i:02d}", "video_id": 2967 if i == 5 else 3000 + i}
                    for i in range(1, 17)
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "new-run"
    with pytest.raises(ValueError, match="boundary"):
        prepare_plan(review, "not-read", "not-read", output)
    assert not output.exists()


def test_lost_retained_state_is_not_called_deletion_or_mask_drift():
    assert lifecycle_state([{"states": [{"id": 1, "state": 2}]}], 0, 1, "A") == "lost"
    assert lifecycle_state([{"states": []}], 0, 1, "A") == "deleted"
    assert lifecycle_state([{"active_ids": [1]}], 0, 1, "B") == "active"
    assert lifecycle_state([{"active_ids": []}], 0, 1, "B") == "deleted"


def test_prompt_audit_checks_actual_cache_boxes_and_correction():
    obs = observation()
    prompt = {
        "id": 7,
        "source": "native_refresh",
        "detector_index": 5,
        "score": obs.score,
        "box_xyxy": obs.box.tolist(),
    }
    record = {"prediction_id": 7, "correction": {"box": obs.box.tolist(), "score": 1.0}}
    audit_prompts([{"frame": 0, "prompt_inputs": [prompt]}], record, [[obs]])
    prompt["box_xyxy"][0] += 1
    with pytest.raises(AssertionError):
        audit_prompts([{"frame": 0, "prompt_inputs": [prompt]}], record, [[obs]])
    controlled = {
        **prompt,
        "source": "controlled_correction",
        "box_xyxy": obs.box.tolist(),
        "score": 1.0,
    }
    audit_prompts([{"frame": 0, "prompt_inputs": [controlled]}], record, [[obs]])


def test_threshold_count_tie_is_not_automatically_exact_mask_tie():
    common = {
        "recovered": True,
        "terminal_three_step_success": True,
        "correct_visible_fraction": 1.0,
    }
    pairs = [
        {
            "model": "A",
            "condition": "yolo",
            "window": 30,
            "R_minus_H_correct_steps": 0,
            "R_minus_H_mean_mask_iou": 0.1,
            "designated_output_changed_steps": [3],
            "H": common,
            "R": common,
            "uncorrected": common,
        },
        {
            "model": "A",
            "condition": "yolo",
            "window": 30,
            "R_minus_H_correct_steps": 0,
            "R_minus_H_mean_mask_iou": 0.0,
            "designated_output_changed_steps": [],
            "H": common,
            "R": common,
            "uncorrected": common,
        },
    ]
    result = aggregate(pairs)[0]
    assert result["independent_event_units"] == 2
    assert result["threshold_count_ties"] == 2
    assert result["exact_target_output_ties"] == 1


def test_kf_state_manipulation_can_differ_even_without_output_changes():
    left = [{"states": [{"id": 1, "mean": [1, 2], "covariance": [[1, 0], [0, 1]]}]}] * 3
    right = [
        {"states": [{"id": 1, "mean": [1, 3], "covariance": [[1, 0], [0, 1]]}]}
    ] * 3
    assert different_KF_state_steps(left, right, 1, 1) == [0, 1]


def test_sam_prompt_input_comparison_excludes_detector_only_metadata():
    left = [
        {"frame": 0, "prompt_inputs": []},
        {
            "frame": 1,
            "prompt_inputs": [
                {"id": 7, "box_xyxy": [1, 2, 3, 4], "score": 0.8, "detector_index": 5}
            ],
        },
    ]
    right = [
        {"frame": 0, "prompt_inputs": []},
        {
            "frame": 1,
            "prompt_inputs": [
                {"id": 7, "box_xyxy": [1, 2, 3, 4], "score": 0.9, "detector_index": 6}
            ],
        },
    ]
    assert prompt_api_schedule(left, 0, 7) == prompt_api_schedule(right, 0, 7)
    right[1]["prompt_inputs"][0]["box_xyxy"][0] = 2
    assert prompt_api_schedule(left, 0, 7) != prompt_api_schedule(right, 0, 7)


def test_completed_local_cohort_has_exact_primary_sample_and_media():
    from tracking_lab import ROOT
    from tracking_lab.recovery_cohort import read_json

    root = ROOT / "runs/recovery-independent-20261020-3080"
    if (
        not (root / "cohort.json").exists()
        or read_json(root / "cohort.json")["status"] != "completed"
    ):
        pytest.skip("Complete local cohort artifacts not present")
    plan = read_json(root / "cohort.json")
    review = read_json(root / "reviewed-events.json")
    assert {r["video_id"] for r in plan["events"]} == {
        r["video_id"] for r in review["events"]
    }
    assert 2967 not in {r["video_id"] for r in plan["events"]}
    assert (
        plan["actual_branches"] == 128 and plan["device"] == "NVIDIA GeForce RTX 3080"
    )
    for row in plan["events"]:
        folder = Path(row["folder"])
        summary = read_json(folder / "summary.json")
        assert summary["status"] == "completed" and len(summary["branches"]) == 8
        assert summary["events"][0]["prefix_exact_replay"]
        assert summary["synchronized_reference"]["historical_B0_different_frames"] == {
            str(row["video_id"]): []
        }
        assert len(list((folder / "visuals").glob("*four-groups.mp4"))) == 2


def test_final_analysis_local_resources_and_sample_counts():
    from html.parser import HTMLParser
    from tracking_lab import ROOT
    from tracking_lab.recovery_cohort import read_json

    folder = ROOT / "runs/recovery-independent-20261020-analysis"
    if not (folder / "results.json").exists():
        pytest.skip("Local analysis artifacts not present")
    results = read_json(folder / "results.json")
    assert results["primary_events"] == 16 and results["branches"] == 128
    assert (
        results["boundary_case_2967_run"] is False
        and len(results["pair_results"]) == 192
    )
    assert all(r["independent_event_units"] == 16 for r in results["aggregates"])
    assert results["numerical_repeat_verification"]["status"] == "passed"

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()
            self.paths = []
            self.images = 0
            self.videos = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs:
                self.ids.add(attrs["id"])
            if tag == "img":
                self.images += 1
            if tag == "video":
                self.videos += 1
            for key in ("src", "href"):
                if key in attrs:
                    self.paths.append(attrs[key])

    parser = Links()
    parser.feed((folder / "RESULTS_ZH.html").read_text(encoding="utf-8"))
    assert parser.images == 64 and parser.videos == 32
    for path in parser.paths:
        assert (
            path[1:] in parser.ids
            if path.startswith("#")
            else (folder / path).is_file()
        ), path
