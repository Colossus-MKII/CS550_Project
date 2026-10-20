"""Selection invariants, independent of new GPU results or H/R interventions."""

import json
from pathlib import Path

import numpy as np
import pytest

from tracking_lab import ROOT, PACKAGE_ROOT
from tracking_lab.common import Instance, digest, mask_box
from tracking_lab.selection_split import OLD_VIDEOS, QUOTAS, SIZES, strong_duplicate
from tracking_lab.selection_screen import choose_candidates
from tracking_lab.selection_preflight import inspect_event


MANIFESTS = ROOT / "manifests"
SPLIT = MANIFESTS / "ytvis2021-200-seed550-v1.json"
QUEUE = MANIFESTS / "independent-candidates-20261020-v2.json"


def local_json(path):
    if not path.exists():
        pytest.skip("Local versioned selection artifacts not present")
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_split_sizes_coverage_groups_and_old_pilots():
    split = local_json(SPLIT)
    all_ids, group_splits = [], {}
    for name, size in SIZES.items():
        rows = split["splits"][name]
        assert len(rows) == size
        all_ids.extend(r["video_id"] for r in rows)
        for row in rows:
            assert group_splits.setdefault(row["group_id"], name) == name
    assert len(all_ids) == len(set(all_ids)) == 226
    assert sum(len(split["splits"][n]) for n in list(SIZES)[:3]) == 200
    dev = {r["video_id"] for r in split["splits"]["development"]}
    assert set(OLD_VIDEOS) <= dev
    for category, quotas in QUOTAS.items():
        assert (
            tuple(
                sum(category in r["categories"] for r in split["splits"][name])
                for name in list(SIZES)[:3]
            )
            == quotas
        )
    for name, minimum in zip(list(SIZES)[:3], (38, 12, 12)):
        assert sum(r["frames"] >= 41 for r in split["splits"][name]) >= minimum


def test_queue_no_old_visual_group_no_heldout_and_new_version_guard(tmp_path):
    split, queue = local_json(SPLIT), local_json(QUEUE)
    dev = {r["video_id"]: r for r in split["splits"]["development"]}
    old_groups = {dev[v]["group_id"] for v in OLD_VIDEOS}
    assert queue["split_sha256"] == digest(SPLIT)
    assert queue["H_R_permitted"] is False
    assert len(queue["video_ids"]) == 32 == len(set(queue["video_ids"]))
    assert len({dev[v]["group_id"] for v in queue["video_ids"]}) == 32
    assert all(
        dev[v]["frames"] >= 41 and dev[v]["group_id"] not in old_groups
        for v in queue["video_ids"]
    )
    assert 2884 not in queue["video_ids"]
    destination = tmp_path / "existing.json"
    destination.touch()
    with pytest.raises(FileExistsError):
        choose_candidates(SPLIT, Path("not-read.json"), destination)


def test_strong_duplicate_requires_two_distinct_sparse_frame_pairs():
    def fingerprint(hashes, sha="a"):
        return {
            "rgb_sha256": sha,
            "width": 640,
            "height": 480,
            "images": [{"phash": h, "mean_rgb": [100, 100, 100]} for h in hashes],
        }

    assert strong_duplicate(fingerprint(["0"]), fingerprint(["f"], "a")) == "exact_rgb"
    assert strong_duplicate(fingerprint(["0"]), fingerprint(["0"], "b")) is None
    assert strong_duplicate(
        fingerprint(["0", "ffffffffffffffff"]),
        fingerprint(["0", "ffffffffffffffff"], "b"),
    )


def instance(identity=1):
    mask = np.zeros((20, 20), bool)
    mask[3:12, 5:14] = True
    return Instance(identity, "person", mask_box(mask), mask, 0.9)


def test_preflight_keeps_first_id_and_separates_missing_box_from_state():
    gt = [[instance()] for _ in range(41)]
    predicted = {
        "A0": [[instance(7)] for _ in gt],
        "B0": [[instance(9)] for _ in gt],
        "YOLO": [[] for _ in gt],
    }
    trace = [{"states": [{"id": 7, "activated": True}]} for _ in gt]
    log = [
        {"frame": t, "active_ids": [9], "actions": [{"action": "refresh", "id": 9}]}
        for t in range(41)
    ]
    row = {"frame": 10, "gt_id": 1, "category": "person"}
    result = inspect_event(
        gt,
        predicted,
        trace,
        log,
        {"sam_retention_steps": 15, "sam_prompt_conf": 0.25},
        row,
    )
    assert result["eligible_common_state"] is True
    assert result["strong_prefix_both_ge3"] is True
    assert result["yolo_correction"] is None
    assert result["anchors"]["A0"]["prediction_id"] == 7
    log[9]["active_ids"] = []
    result = inspect_event(
        gt,
        predicted,
        trace,
        log,
        {"sam_retention_steps": 15, "sam_prompt_conf": 0.25},
        row,
    )
    assert result["eligible_common_state"] is False
    assert "B0: designated state already deleted" in result["eligibility_reasons"]


def test_selection_drivers_do_not_call_intervention_engines():
    import ast

    for name in (
        "selection_split.py",
        "selection_screen.py",
        "selection_baselines.py",
        "selection_preflight.py",
        "selection_report.py",
    ):
        source = ast.parse((PACKAGE_ROOT / name).read_text(encoding="utf-8"))
        for node in ast.walk(source):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {
                    "recovery",
                    "recovery_long",
                    "recovery_engines",
                }
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"reset_sam_target", "run_recovery", "train"}


def test_review_is_not_execution_approval_and_exposes_missing_gt():
    from collections import Counter

    review = local_json(MANIFESTS / "independent-events-review-20261020-v2.json")
    events = review["events"]
    assert review["approved"] is False and review["H_R_run"] is False
    assert "NOT_executable" in review["status"]
    assert Counter(e["scene"] for e in events) == {
        s: 4 for s in ("stable", "motion", "competition", "occlusion")
    }
    assert (
        len({e["video_id"] for e in events})
        == len({e["group_id"] for e in events})
        == 16
    )
    assert review["split_sha256"] == digest(SPLIT)
    assert review["queue_sha256"] == digest(QUEUE)
    assert review["endpoint_limited_event_ids"] == ["E05"]
    for event in events:
        assert event["eligible_common_state"] and event["strong_prefix_both_ge3"]
        assert event["yolo_correction"] is not None
        assert event["approved"] is False and event["H_R_run"] is False
        assert event["frame"] >= 10 and event["frame"] + 30 < event["frames"]
        for values in event["automatic_baseline_followup_NOT_HR"].values():
            assert values["GT_visible_steps"] + len(values["GT_absent_steps"]) == 30
            if event["scene"] == "stable":
                assert (
                    values["qualified_fixed_id_steps"]
                    == values["GT_visible_steps"]
                    == 30
                )
    boundary = next(e for e in events if e["event_id"] == "E05")
    assert boundary["visible_followup"] == 12
    assert (
        boundary["observability_at_planned_readouts"]["8"]["GT_visible_at_endpoint"]
        is True
    )
    assert (
        boundary["observability_at_planned_readouts"]["20"]["GT_visible_at_endpoint"]
        is False
    )
    assert (
        boundary["observability_at_planned_readouts"]["30"]["GT_visible_at_endpoint"]
        is False
    )


@pytest.mark.parametrize("version,image_count", [(2, 32), (3, 34)])
def test_offline_review_images_and_fragment_links_exist(version, image_count):
    from html.parser import HTMLParser

    review = local_json(
        MANIFESTS / f"independent-events-review-20261020-v{version}.json"
    )
    path = Path(review["report_file"])
    if not path.exists():
        pytest.skip("Local RGB review package not present")

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.links, self.images = set(), [], []

        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            if "id" in attrs:
                self.ids.add(attrs["id"])
            if tag == "a" and "href" in attrs:
                self.links.append(attrs["href"])
            if tag == "img":
                self.images.append(attrs["src"])

    parsed = Parser()
    parsed.feed(path.read_text(encoding="utf-8"))
    assert len(parsed.images) == image_count
    for image in parsed.images:
        assert (path.parent / image).is_file()
    for link in parsed.links:
        assert (
            link[1:] in parsed.ids
            if link.startswith("#")
            else (path.parent / link).is_file()
        )


def test_v3_replaces_only_e05_and_retains_pinned_boundary_outside_main():
    previous_path = MANIFESTS / "independent-events-review-20261020-v2.json"
    previous = local_json(previous_path)
    current = local_json(MANIFESTS / "independent-events-review-20261020-v3.json")
    assert current["approved"] is False and current["H_R_run"] is False
    assert current["primary_event_count"] == len(current["events"]) == 16
    assert current["boundary_case_count"] == len(current["boundary_cases"]) == 1
    assert current["scene_counts"] == previous["scene_counts"]
    assert current["split_sha256"] == previous["split_sha256"] == digest(SPLIT)
    assert current["queue_sha256"] == previous["queue_sha256"] == digest(QUEUE)
    assert current["endpoint_limited_event_ids"] == []
    assert current["full_GT_visible_window_count"] == 14
    for index, old in enumerate(previous["events"]):
        new = current["events"][index]
        if old["event_id"] == "E05":
            assert (new["video_id"], new["gt_id"], new["frame"]) == (2705, 1, 16)
            assert new["visible_followup"] == 30 and new["complete_GT_visible_followup"]
            assert new["require_complete_GT_visible_followup"] is True
            assert (
                new["eligible_common_state"]
                and new["strong_prefix_both_ge3"]
                and new["yolo_correction"]
            )
            for values in new["automatic_baseline_followup_NOT_HR"].values():
                assert [v["frame"] for v in values["values"]] == list(range(17, 47))
                assert (
                    values["GT_visible_steps"] == 30 and values["GT_absent_steps"] == []
                )
        else:
            for key, value in old.items():
                if key not in {"evidence_image", "detector_image"}:
                    assert new[key] == value, (old["event_id"], key)
    assert 2967 not in {e["video_id"] for e in current["events"]}
    boundary = current["boundary_cases"][0]
    assert (
        boundary["event_id"],
        boundary["video_id"],
        boundary["gt_id"],
        boundary["frame"],
    ) == ("BC01", 2967, 3, 14)
    assert boundary["visible_followup"] == 12 and boundary["readout_endpoint_limited"]
    assert boundary["included_in_primary_counts"] is False
    assert boundary["included_in_complete_long_window_stats"] is False
    assert boundary["execution_authorized"] is False and boundary["H_R_run"] is False
    assert boundary["source_review_sha256"] == digest(previous_path)
