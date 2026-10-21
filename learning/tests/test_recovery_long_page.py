"""Portable presentation fixtures: no neural models, video decoder or real runs."""

import ast
import csv
import json
from pathlib import Path
import re

import pytest

from learning.recovery_page import EVENTS, GROUPS, digest, import_recovery
from learning.recovery_long_data import CODE_LONG, PAGES, TABLES, import_long, read_long
from learning.report import refresh_report, write_report
from learning.tests.test_recovery_page import make_batch
from learning.tests.test_study import Page


def make_long_batch(tmp_path):
    previous, output = make_batch(tmp_path)
    old = import_recovery(previous, output)
    study = tmp_path / "long-study"
    study.mkdir()

    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def curve_result(t, cat, group, skipped):
        curve, streak = [], 0
        for offset in range(1, 31):
            correct = (
                offset <= 15
                if cat
                else group.endswith("R") and offset >= (8 if skipped else 7)
            )
            streak = streak + 1 if correct else 0
            curve.append(
                {
                    "frame": t + offset,
                    "offset": offset,
                    "visible": True,
                    "mask_iou": 0.7 if correct else 0.3,
                    "correct": correct,
                    "success_streak": streak,
                    "output_present": True,
                }
            )
        confirmed = next((r["offset"] for r in curve if r["success_streak"] == 3), None)
        summary = {
            "mean_visible_mask_iou": sum(r["mask_iou"] for r in curve) / 30,
            "correct_visible_steps": sum(r["correct"] for r in curve),
            "visible_steps": 30,
            "longest_correct_streak": max(r["success_streak"] for r in curve),
            "relapses": int(cat),
            "recovery_confirmed_offset": confirmed,
        }
        return {"curve": curve, "summary": summary}

    cfg = {
        "window": 30,
        "report_windows": [8, 20, 30],
        "mask_iou_threshold": 0.5,
        "streak_required": 3,
        "conditions": ["yolo", "reference"],
    }
    scores, runs, repeats, video_proofs = [], {}, [], []
    for mode in ("normal", "skip"):
        source = tmp_path / ("long-" + mode)
        source.mkdir()
        config = {**cfg, "sam_skip_next_refresh": mode == "skip", "role": mode}
        branches = []
        for event in old["events"]:
            cat = EVENTS[event["name"]] == "cat"
            t = event["frame"]
            for condition in cfg["conditions"]:
                for group in GROUPS:
                    folder = f'{event["name"]}/{condition}/{group}'
                    result = curve_result(
                        t, cat, group, mode == "skip" and group.startswith("B")
                    )
                    save(source / folder / "recovery.json", result)
                    record = {
                        "event": event["name"],
                        "condition": condition,
                        "group": group,
                        "folder": folder,
                        "prediction_id": 1,
                        **result["summary"],
                    }
                    branches.append(record)
                    for window in (8, 20, 30):
                        rows = result["curve"][:window]
                        confirmed = next(
                            (r["offset"] for r in rows if r["success_streak"] == 3),
                            None,
                        )
                        scores.append(
                            {
                                "mode": mode,
                                "event": event["name"],
                                "condition": condition,
                                "group": group,
                                "window": window,
                                "mean_visible_mask_iou": sum(
                                    r["mask_iou"] for r in rows
                                )
                                / window,
                                "correct_visible_steps": sum(
                                    r["correct"] for r in rows
                                ),
                                "visible_steps": window,
                                "longest_correct_streak": max(
                                    r["success_streak"] for r in rows
                                ),
                                "relapses": int(cat and window > 15),
                                "recovery_confirmed_offset": confirmed,
                            }
                        )
                    stages = [
                        {
                            "tracks": [{"external_id": 1}],
                            "detections": [
                                {"detector_index": 1},
                                {"detector_index": 3},
                            ],
                            "assignment_cost": [[0.6, 0.7]],
                            "matches": [[0, 0]],
                        }
                    ]
                    save(
                        source / folder / "state-trace.json",
                        [
                            {
                                "frame": frame,
                                "active_ids": [1],
                                "output_ids": [1],
                                "actions": [],
                                "assignments": [
                                    {"category": "person", "stages": stages}
                                ],
                            }
                            for frame in range(t + 31)
                        ],
                    )
                base = source / f'visuals/{event["name"]}-{condition}'
                base.parent.mkdir(exist_ok=True)
                for ending in (
                    "curves.png",
                    "four-groups.mp4",
                    *(f"step{t+i}.png" for i in (1, 3, 30)),
                ):
                    path = Path(str(base) + "-" + ending)
                    path.write_bytes(b"curated fixture only")
                    if ending.endswith(".mp4"):
                        video_proofs.append(
                            {
                                "run": source.name,
                                "file": path.name,
                                "decoded_frames": 33,
                                "sha256": digest(path),
                            }
                        )
        hashes = {}
        for name in CODE_LONG:
            path = source / ("code/" + name + ".txt")
            path.parent.mkdir(exist_ok=True)
            path.write_text("# fixture source\n", encoding="utf-8")
            hashes[name] = digest(path)
        summary = {
            "status": "completed",
            "configuration": config,
            "events": old["events"],
            "branches": branches,
            "source_sha256": hashes,
            "baseline_summary_sha256": old["baseline_summary_sha256"],
            "synchronized_reference": {
                "historical_B0_different_frames": {"2718": [], "2689": []}
            },
        }
        save(source / "summary.json", summary)
        save(source / "config.json", config)
        save(source / "verification.json", {"status": "passed"})
        save(source / "private-login.json", {"secret": "not public"})
        runs[mode] = source
        repeats.append(
            {
                "run": source.name,
                "status": "passed",
                "branches": 16,
                "state_traces_exact": 16,
                "first_summary_sha256": digest(source / "summary.json"),
            }
        )
    with (study / "checkpoint-scores.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    for name in TABLES:
        if name != "checkpoint-scores.csv":
            (study / name).write_text("fixture,table\n", encoding="utf-8")
    for event in EVENTS:
        for condition in cfg["conditions"]:
            (study / f"{event}-{condition}-refresh-curves.png").write_bytes(
                b"fixture curve"
            )
    save(
        study / "study-verification.json",
        {
            "status": "passed",
            "normal_run": str(runs["normal"]),
            "skip_run": str(runs["skip"]),
            "previous_run": str(previous),
            "run_summary_sha256": {
                str(p): digest(p / "summary.json") for p in [*runs.values(), previous]
            },
            "compatibility_checks": [{"old_8_steps_exact": True}] * 16,
            "treatment_checks": [],
        },
    )
    save(
        study / "final-verification.json",
        {
            "status": "passed",
            "study_verification_sha256": digest(study / "study-verification.json"),
            "repeat_checks": repeats,
            "video_checks": video_proofs,
        },
    )
    return study, output


def test_long_import_pages_and_reading_links_preserve_old_evidence(tmp_path):
    study, output = make_long_batch(tmp_path)
    old = {
        p.relative_to(output): p.read_bytes()
        for p in (output / "recovery-results").rglob("*")
        if p.is_file()
    }
    data = import_long(study, output)
    write_report(output, {"status": "completed"})
    assert read_long(output) == data
    assert all((output / p).read_bytes() == value for p, value in old.items())
    assert str(tmp_path) not in json.dumps(data)
    assert not list((output / data["prefix"]).rglob("summary.json"))
    assert not list((output / data["prefix"]).rglob("private-login.json"))
    texts = [(output / name).read_text(encoding="utf-8") for name in PAGES]
    assert Page(texts[0]).ids == Page(texts[1]).ids
    for text in texts:
        page = Page(text)
        assert len(page.ids) == len(set(page.ids))
        assert text.count("<video ") == 8 and text.count('preload="none"') == 8
        assert text.count("data-seek=") == 24
        assert all((output / src).is_file() for src in page.sources)
        assert "@@" not in text
    english = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", texts[1], flags=re.S)
    english = re.sub(r"<[^>]+>", "", english).replace("中文", "")
    assert not re.search(r"[\u4e00-\u9fff]", english)
    for slug in ("index", "runs", "recovery", "results", "program", "experiments"):
        for suffix in ("", ".en"):
            assert f'href="recovery-long{suffix}.html' in (
                output / f"{slug}{suffix}.html"
            ).read_text(encoding="utf-8")
    (output / "summary.json").write_text('{"status":"completed"}', encoding="utf-8")
    refresh_report(output)
    assert list(output.glob("recovery-long.before-refresh-*.html"))


def test_long_proof_tampering_and_checkpoint_inconsistency_rejected(tmp_path):
    study, output = make_long_batch(tmp_path)
    proof = study / "study-verification.json"
    original = proof.read_bytes()
    proof.write_text("{}")
    with pytest.raises((KeyError, ValueError)):
        import_long(study, output)
    proof.write_bytes(original)
    scores = study / "checkpoint-scores.csv"
    scores.write_text(
        scores.read_text(encoding="utf-8-sig").replace("0.3,", "0.9,", 1),
        encoding="utf-8-sig",
    )
    # Also catches alternate floating representations: deliberately alter a row.
    rows = list(csv.DictReader(scores.open(encoding="utf-8-sig")))
    rows[0]["mean_visible_mask_iou"] = "0.99"
    with scores.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Checkpoint"):
        import_long(study, output)


def test_long_archive_tampering_and_predecessor_changes_rejected(tmp_path):
    study, output = make_long_batch(tmp_path)
    data = import_long(study, output)
    target = output / data["prefix"] / "checkpoint-pairs.csv.txt"
    target.write_text("changed")
    with pytest.raises(ValueError, match="alias fingerprint"):
        read_long(output)
    target.write_bytes((output / data["prefix"] / "checkpoint-pairs.csv").read_bytes())
    active = output / "recovery-results/manifest.json"
    old = json.loads(active.read_text())
    old["run"] = "different"
    active.write_text(json.dumps(old), encoding="utf-8")
    with pytest.raises(ValueError):
        read_long(output)


def test_long_builders_never_import_models():
    from learning import recovery_long_data, recovery_long_page

    for module in (recovery_long_data, recovery_long_page):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots = (
                [a.name.split(".")[0] for a in node.names]
                if isinstance(node, ast.Import)
                else (
                    [(node.module or "").split(".")[0]]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
            )
            assert not set(roots) & {"tracking_lab", "torch", "sam2", "ultralytics"}
