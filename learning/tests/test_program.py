"""Global-first program navigation must be bilingual, factual and read-only."""

import ast
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest

from learning.program_page import (
    PAGES,
    SOURCE_FILES,
    SOURCE_ROOT,
    read_evidence,
    write_program_pages,
)
from learning.report import refresh_report, write_report
from learning.tests.test_results import make_source
from learning.pilot_page import import_results
from learning.tests.test_study import Page


def test_builder_never_imports_experiment_or_model_runtime():
    import learning.program_page as builder

    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
    banned = {"tracking_lab", "torch", "ultralytics", "sam2", "pilot"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in banned for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned


def test_program_pages_have_same_structure_and_usable_source_links(tmp_path):
    before = {
        name: sha256((SOURCE_ROOT / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }
    write_report(tmp_path, {"status": "completed"})
    pages = [(tmp_path / name).read_text(encoding="utf-8") for name in PAGES]
    assert Page(pages[0]).ids == Page(pages[1]).ids
    for name, text in zip(PAGES, pages):
        page = Page(text)
        assert len(page.ids) == len(set(page.ids))
        assert "@@" not in text
        assert text.count("data-program-panel=") == 8
        assert 'id="program-controls" hidden' in text
        assert not page.sources  # No fake evidence when no run was imported.
        for key in (
            "map",
            "steps",
            "calls",
            "evidence",
            "recovery",
            "criteria",
            "support",
            "next",
        ):
            assert key in page.ids
        assert all(group in text for group in ("A-H", "A-R", "B-H", "B-R"))
        for href in page.links:
            target = urlsplit(href)
            assert not target.scheme and not target.netloc
            filename = unquote(target.path) or name
            path = tmp_path / filename
            assert path.is_file(), (name, href)
            if target.fragment:
                assert (
                    unquote(target.fragment)
                    in Page(path.read_text(encoding="utf-8")).ids
                )
    english = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", pages[1], flags=re.S)
    english = re.sub(r"<[^>]+>", "", english).replace("中文", "")
    assert not re.search(r"[\u4e00-\u9fff]", english)
    manifest = json.loads((tmp_path / "program-code/manifest.json").read_text())
    assert manifest["kind"] == "current-source-reference"
    assert set(manifest["files"]) == set(SOURCE_FILES)
    for filename, entry in manifest["files"].items():
        raw = (tmp_path / "program-code" / (filename + ".txt")).read_bytes()
        assert sha256(raw).hexdigest() == entry["sha256"] == before[filename]
        for suffix in ("", ".en"):
            text = (
                tmp_path / "program-code" / (filename + suffix + ".html")
            ).read_text(encoding="utf-8")
            for number in entry["functions"].values():
                assert f"L{number}" in Page(text).ids
    assert before == {
        name: sha256((SOURCE_ROOT / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }


def test_home_and_related_pages_offer_obvious_entry(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for suffix in ("", ".en"):
        home = (tmp_path / f"index{suffix}.html").read_text(encoding="utf-8")
        assert f'href="program{suffix}.html"' in home
        assert f'href="program{suffix}.html"' in home.split('id="project-navigation"',1)[1].split('</nav>',1)[0]
        assert 'id="latest-results-link"' in home
        protocol = (tmp_path / f"experiments{suffix}.html").read_text(encoding="utf-8")
        assert f'href="program{suffix}.html"' in protocol


def test_evidence_is_verified_and_never_mutated(tmp_path):
    source = tmp_path / "verified-run"
    make_source(source)
    output = tmp_path / "site"
    output.mkdir()
    imported = import_results(source, output)
    old = {
        str(path.relative_to(output)): path.read_bytes()
        for path in (output / "pilot-results").rglob("*")
        if path.is_file()
    }
    write_program_pages(output)
    assert old == {
        str(path.relative_to(output)): path.read_bytes()
        for path in (output / "pilot-results").rglob("*")
        if path.is_file()
    }
    for name in PAGES:
        text = (output / name).read_text(encoding="utf-8")
        assert 'id="program-pilot-scores"' in text
        assert "<td>50.0</td>" in text and "<td>70.0</td>" in text
        assert "C:/private" not in text
    raw = output / imported["prefix"] / "metrics.json"
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        read_evidence(output)


def test_unsafe_evidence_prefix_is_rejected(tmp_path):
    path = tmp_path / "pilot-results"
    path.mkdir()
    (path / "manifest.json").write_text(json.dumps({"prefix": "../private/"}))
    with pytest.raises(ValueError, match="Unsafe"):
        read_evidence(tmp_path)


def test_refresh_preserves_previous_map(tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    for name in PAGES:
        (tmp_path / name).write_text("OLD " + name)
    refresh_report(tmp_path)
    for name in PAGES:
        backups = list(tmp_path.glob(name[:-5] + ".before-refresh-*.html"))
        assert len(backups) == 1
        assert backups[0].read_text() == "OLD " + name
