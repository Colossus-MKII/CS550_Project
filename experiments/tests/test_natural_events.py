"""Natural-event rules; no models or GPU needed."""

import json
from pathlib import Path

import numpy as np
import pytest

from tracking_lab.common import Instance, mask_box
from tracking_lab.natural_events import failure_label, choose_events, has_correct_run, fixed_id_curve
from tracking_lab.natural_recovery import prepare


def test_three_failures_need_a_previous_correct_streak():
    assert failure_label([.8,.8,.8,.2,.1,.0], 5) == "persistent_failure"
    assert failure_label([.0,.1,.0,.2,.1,.0], 5) != "persistent_failure"
    assert failure_label([.8,.8,.8,.2,None,.0], 5) != "persistent_failure"
    assert not has_correct_run([.8,.8,None,.8,.8])


def test_current_low_frame_alone_is_not_persistent_failure():
    assert failure_label([.8,.8,.8,.7,.6,.4], 5) == "transient_failure"
    assert failure_label([.8,.8,.8,.7,.6,.5], 5) == "maintenance"


def test_failure_label_does_not_use_post_correction_predictions():
    prefix = [.8,.8,.8,.2,.1,.0]
    assert failure_label(prefix+[1.0]*30, 5) == failure_label(prefix+[0.0]*30, 5)


def test_identity_is_not_reselected_after_an_identity_switch():
    mask = np.zeros((8,8), bool)
    mask[2:6,2:6] = True
    def obj(identity):
        return Instance(identity, "person", mask_box(mask), mask)
    gt = [[obj(1)] for _ in range(6)]
    pred = [[obj(7)] for _ in range(3)] + [[obj(8)] for _ in range(3)]
    values, identity, anchor = fixed_id_curve(gt,pred,1,"person")
    assert (identity,anchor) == (7,0)
    assert values == [1.0,1.0,1.0,0.0,0.0,0.0]
    assert failure_label(values,5) == "persistent_failure"


def test_existing_output_and_empty_selection_are_rejected(tmp_path):
    with pytest.raises(FileExistsError):
        prepare("not-read.json",tmp_path)
    frozen = tmp_path/"frozen.json"
    frozen.write_text(json.dumps({"events": []}), encoding="utf-8")
    with pytest.raises(ValueError,match="No eligible"):
        prepare(frozen,tmp_path/"new")
    assert not (tmp_path/"new").exists()


def test_selection_one_per_video_prioritizes_unused_and_never_requires_both_fail():
    rows = [
        {"video_id": v, "frame": t, "gt_id": 1, "labels": {"A0": a, "B0": b}}
        for v,t,a,b in [(2,8,"maintenance","persistent_failure"),
                        (1,9,"maintenance","persistent_failure"),
                        (1,7,"persistent_failure","maintenance"),
                        (3,8,"persistent_failure","maintenance")]
    ]
    chosen = choose_events(rows, {2}, per_model=1)
    assert [r["video_id"] for r in chosen] == [1,3]
    assert chosen[0]["labels"]["A0"] == "maintenance"
    assert chosen[0]["frame"] == 9


def test_completed_natural_supplement_has_local_media_and_separated_labels():
    from html.parser import HTMLParser
    from tracking_lab import ROOT
    from tracking_lab.natural_events import read_json

    root = ROOT / "runs/recovery-natural-20261021-analysis"
    if not (root / "results.json").exists():
        pytest.skip("Completed local natural supplement not present")
    result = read_json(root / "results.json")
    checks = read_json(root / "verification.json")
    assert result["branches"] == result["primary_events"] * 8
    assert result["paired_windows"] == result["primary_events"] * 12
    assert checks["status"] == checks["repeat"]["status"] == "passed"
    assert all("pre_event_label" in r for r in result["pair_results"])
    assert {r["pre_event_label"] for r in result["aggregates"]} >= {"persistent_failure","maintenance"}

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
            self.videos = 0
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            self.videos += tag == "video"
            for key in ("href","src"):
                if key in attrs:
                    self.links.append(attrs[key])
    parser = Links()
    parser.feed((root/"RESULTS_ZH.html").read_text(encoding="utf-8"))
    assert parser.videos == result["primary_events"] * 2
    assert all((root/path).is_file() for path in parser.links)


def test_reference_only_archive_preserves_missing_YOLO_and_four_groups():
    from tracking_lab import ROOT
    from tracking_lab.natural_events import read_json

    root = ROOT/"runs/recovery-natural-reference-20261021-3080"
    if not (root/"cohort.json").exists() or read_json(root/"cohort.json")["status"]!="completed":
        pytest.skip("Complete local reference-only run not present")
    plan=read_json(root/"cohort.json")
    frozen=read_json(root/"frozen-events.json")
    assert plan["conditions"]==["reference"]
    assert plan["actual_branches"]==4*len(plan["events"])
    assert plan["repeat_verification"]["status"]=="passed"
    for e in frozen["events"]:
        assert e["yolo_correction"] is None
        assert e["labels"]["B0"]=="persistent_failure"
    for e in plan["events"]:
        summary=read_json(Path(e["folder"])/"summary.json")
        assert {b["condition"] for b in summary["branches"]}=={"reference"}
        assert {b["group"] for b in summary["branches"]}=={"A-H","A-R","B-H","B-R"}
    analysis=ROOT/"runs/recovery-natural-reference-20261021-analysis"
    if (analysis/"verification.json").exists():
        checks=read_json(analysis/"verification.json")
        assert all(e["independent_Byte_branch_replay"]["branches"]==2 for e in checks["events"])


def test_portable_event_index_preserves_split_sources_and_membership():
    manifests=Path(__file__).resolve().parents[1]/"manifests"
    read=lambda name:json.loads((manifests/name).read_text(encoding="utf-8"))
    index=read("natural-events-20261021-v1.json")
    split=read(index["split"])
    development={r["video_id"] for r in split["splits"]["development"]}
    assert len(index["events"])==7
    assert len({e["video_id"] for e in index["events"]})==7
    assert {e["video_id"] for e in index["events"]}<=development
    assert all(e["video_id"]!=2967 for e in index["events"])
    assert sum(4*len(e["conditions"]) for e in index["events"])==index["main_branches"]==52
    assert index["history_pollution_included"] is False
    reference=next(e for e in index["events"] if e["key"]=="reference-S01")
    assert reference["conditions"]==["reference"]
    assert reference["YOLO_correction"]=="unavailable_under_frozen_thresholds"
