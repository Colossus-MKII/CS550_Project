"""H/R presentation imports verified artifacts, never executes inference."""

import ast
import json
from pathlib import Path
import re

import pytest

from learning.pilot_page import import_results
from learning.recovery_page import (
    CODE,
    EVENTS,
    GROUPS,
    PAGES,
    digest,
    import_recovery,
    read_recovery,
)
from learning.report import write_report, refresh_report
from learning.tests.test_results import make_source
from learning.tests.test_study import Page


def make_batch(tmp_path):
    baseline = tmp_path / "baseline"
    make_source(baseline)
    output = tmp_path / "site"
    output.mkdir()
    import_results(baseline, output)
    source = tmp_path / "rider-cat"
    source.mkdir()

    def save(relative, value):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    config = {
        "conditions": ["yolo", "reference"],
        "window": 8,
        "mask_iou_threshold": 0.5,
        "streak_required": 3,
    }
    events = [
        {
            "name": name,
            "video_id": 2718 if alias == "rider" else 2689,
            "gt_id": 1 if alias == "rider" else 2,
            "frame": 14 if alias == "rider" else 20,
            "anchors": {m: {"prediction_id": 1} for m in ("A0", "B0")},
        }
        for name, alias in EVENTS.items()
    ]
    scores = {
        "mean_visible_mask_iou": 0.5,
        "correct_visible_steps": 8,
        "visible_steps": 8,
        "longest_correct_streak": 8,
        "relapses": 0,
    }
    branches = []
    for event in events:
        for condition in config["conditions"]:
            key = event["name"] + "-" + condition
            save(
                f"visuals/{key}-baseline.json",
                {m: {"summary": scores, "curve": []} for m in ("A", "B")},
            )
            for ending in (
                "curves.png",
                "four-groups.mp4",
                *(f'step{event["frame"]+n}.png' for n in (1, 3, 8)),
            ):
                path = source / f"visuals/{key}-{ending}"
                path.write_bytes(b"curated media fixture")
            for group in GROUPS:
                folder = f'{event["name"]}/{condition}/{group}'
                save(folder + "/recovery.json", {"summary": scores, "curve": []})
                branches.append(
                    {
                        "event": event["name"],
                        "condition": condition,
                        "group": group,
                        "folder": folder,
                        **scores,
                    }
                )
    hashes = {}
    for name in CODE:
        path = source / ("code/" + name + ".txt")
        path.parent.mkdir(exist_ok=True)
        path.write_text("# actual inference source fixture\n")
        hashes[name] = digest(path)
    summary = {
        "status": "completed",
        "baseline_source": str(baseline),
        "baseline_summary_sha256": digest(baseline / "summary.json"),
        "synchronized_reference": {
            "historical_B0_different_frames": {"2718": [], "2689": []}
        },
        "configuration": config,
        "events": events,
        "branches": branches,
        "source_sha256": hashes,
        "environment": {"device": "fixture GPU"},
        "created_utc": "2026-10-18",
        "weights": {},
    }
    save("summary.json", summary)
    save("verification.json", {"status": "passed", "branches": 16})
    save(
        "repeat-verification.json",
        {
            "status": "passed",
            "branches": 16,
            "first_summary_sha256": digest(source / "summary.json"),
            "second_summary_sha256": "other",
            "saved_branch_frames": 416,
            "masks_compared": 1123,
        },
    )
    for name in (
        "config.json",
        "events.json",
        "paired-differences.csv",
        "frame-curves.csv",
    ):
        save(name, {})
    save("association-audit.json", {"frames": []})
    save("private-login.json", {"not": "public"})
    return source, output


def test_hr_import_is_curated_bilingual_and_preserves_originals(tmp_path):
    source, output = make_batch(tmp_path)
    before = {
        p.relative_to(source).as_posix(): p.read_bytes()
        for p in source.rglob("*")
        if p.is_file()
    }
    baseline = (output / "pilot-results/manifest.json").read_bytes()
    data = import_recovery(source, output)
    write_report(output, {"status": "completed"})
    assert read_recovery(output) == data
    assert (output / "pilot-results/manifest.json").read_bytes() == baseline
    public = json.dumps(data)
    assert str(source) not in public and str(source.parent / "baseline") not in public
    assert not (output / data["prefix"] / "summary.json").exists()
    assert not (output / data["prefix"] / "private-login.json").exists()
    pages = [(output / name).read_text(encoding="utf-8") for name in PAGES]
    assert Page(pages[0]).ids == Page(pages[1]).ids
    for text in pages:
        page = Page(text)
        assert len(page.ids) == len(set(page.ids))
        assert text.count("<video ") == 4 and text.count("data-hr-condition=") == 4
        assert "hr-association-evidence" in page.ids
        assert all((output / url).is_file() for url in page.sources)
        assert "@@" not in text
    visible = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", pages[1], flags=re.S)
    visible = re.sub(r"<[^>]+>", "", visible).replace("中文", "")
    assert not re.search(r"[\u4e00-\u9fff]", visible)
    for slug in ("index", "results", "program", "experiments", "runs"):
        for suffix in ("", ".en"):
            assert f'href="recovery{suffix}.html"' in (
                output / f"{slug}{suffix}.html"
            ).read_text(encoding="utf-8")
    assert before == {
        p.relative_to(source).as_posix(): p.read_bytes()
        for p in source.rglob("*")
        if p.is_file()
    }


def test_bad_repeat_proof_and_tampered_artifacts_are_rejected(tmp_path):
    source, output = make_batch(tmp_path)
    path = source / "repeat-verification.json"
    repeat = json.loads(path.read_text())
    repeat["first_summary_sha256"] = "wrong"
    path.write_text(json.dumps(repeat))
    with pytest.raises(ValueError, match="Repeat proof"):
        import_recovery(source, output)
    repeat["first_summary_sha256"] = digest(source / "summary.json")
    path.write_text(json.dumps(repeat))
    data = import_recovery(source, output)
    target = output / data["prefix"] / "visuals/cat-stable-control-yolo-curves.png"
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="fingerprint"):
        read_recovery(output)


def test_refresh_backs_up_hr_and_builder_does_not_import_models(tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    for name in PAGES:
        (tmp_path / name).write_text("old " + name)
    refresh_report(tmp_path)
    for name in PAGES:
        assert list(tmp_path.glob(name[:-5] + ".before-refresh-*.html"))
        assert "No verified H/R" in (tmp_path / "recovery.en.html").read_text(
            encoding="utf-8"
        )
    import learning.recovery_page as builder

    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                a.name.split(".")[0]
                not in {"tracking_lab", "torch", "sam2", "ultralytics"}
                for a in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in {
                "tracking_lab",
                "torch",
                "sam2",
                "ultralytics",
            }


def test_changed_active_baseline_cannot_silently_relabel_hr(tmp_path):
    source, output = make_batch(tmp_path)
    import_recovery(source, output)
    path = output / "pilot-results/manifest.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    baseline["run"] = "a-different-baseline"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(ValueError, match="baseline no longer matches"):
        read_recovery(output)
