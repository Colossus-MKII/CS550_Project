"""The project homepage prioritizes experiments; lessons remain intact."""

from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from learning.pilot_page import import_results
from learning.report import refresh_report, write_report
from learning.tests.test_results import make_source
from learning.tests.test_study import Page
from learning.workbench import HANDBOOK_PAGES, PAGES


def test_project_home_is_not_the_teaching_handbook(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for suffix in ("", ".en"):
        text = (tmp_path / f"index{suffix}.html").read_text(encoding="utf-8")
        parsed = Page(text)
        assert len(parsed.ids) == len(set(parsed.ids))
        for key in (
            "overview",
            "runs",
            "results",
            "next",
            "pipeline",
            "dataset",
            "proposal",
            "resources",
        ):
            assert key in parsed.ids
        assert parsed.ids.index("results") < parsed.ids.index("resources")
        assert 'id="latest-results-link"' in text
        assert 'id="learning-entry-link"' in text
        assert parsed.ids.index("pathways") < parsed.ids.index("results")
        assert 'class="project-pathways"' in text
        for chapter in (1, 3, 4, 6):
            assert f'href="handbook{suffix}.html#chapter-{chapter}"' in text
        assert 'id="course-progress"' not in text
        assert 'id="lesson-data"' not in text
        assert "<video" not in text
        assert 'id="handbook-link"' in text
        assert "window.cs550LegacyIds=" in text
        assert "routeLegacyBookmark" in text
        assert (
            'id="project-score-table"' not in text
        )  # No synthetic pilot in an empty site.
        book = (tmp_path / f"handbook{suffix}.html").read_text(encoding="utf-8")
        assert book.count('data-complete="chapter-') == 7
        assert book.count('class="lesson-connection"') == 6
        assert (
            'id="start-learning-link" class="button primary" href="#chapter-1"' in book
        )
        for chapter in (1, 2, 3, 4, 6, 7):
            assert f'id="lesson-connection-{chapter}"' in book
        assert 'id="lesson-data"' in book


def test_every_project_page_has_consistent_navigation_and_valid_links(tmp_path):
    for name, content in (
        ("summary.json", "{}"),
        ("environment.txt", "fixture"),
        ("yolo_records.jsonl", ""),
        ("sam2_records.jsonl", ""),
    ):
        (tmp_path / name).write_text(content, encoding="utf-8")
    write_report(tmp_path, {"status": "completed"})
    filenames = (
        *PAGES,
        *HANDBOOK_PAGES,
        "results.html",
        "results.en.html",
        "program.html",
        "program.en.html",
        "dataset.html",
        "dataset.en.html",
        "experiments.html",
        "experiments.en.html",
        "math.html",
        "math.en.html",
        "research.html",
        "research.en.html",
    )
    for filename in filenames:
        text = (tmp_path / filename).read_text(encoding="utf-8")
        assert text.count('id="project-navigation"') == 1
        parsed = Page(text)
        assert len(parsed.ids) == len(set(parsed.ids))
        assert "@@" not in text
        if filename.split(".")[0] in {"program", "results", "dataset", "experiments"}:
            assert 'id="page-context"' in text
        for href in parsed.links:
            target = urlsplit(href)
            if target.scheme or target.netloc:
                continue
            path = (
                (tmp_path / unquote(target.path))
                if target.path
                else tmp_path / filename
            )
            assert path.is_file(), (filename, href)
            if target.fragment and path.suffix == ".html":
                assert (
                    unquote(target.fragment)
                    in Page(path.read_text(encoding="utf-8")).ids
                ), (filename, href)
    for filename in PAGES:
        if ".en." not in filename:
            continue
        text = (tmp_path / filename).read_text(encoding="utf-8")
        visible = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.S)
        visible = re.sub(r"<[^>]+>", "", visible).replace("中文", "")
        assert not re.search(r"[\u4e00-\u9fff]", visible)


def test_imported_run_is_displayed_without_mutating_evidence(tmp_path):
    source = tmp_path / "verified-run"
    make_source(source)
    output = tmp_path / "site"
    output.mkdir()
    import_results(source, output)
    before = {
        str(p.relative_to(output)): p.read_bytes()
        for p in (output / "pilot-results").rglob("*")
        if p.is_file()
    }
    write_report(output, {"status": "completed"})
    assert before == {
        str(p.relative_to(output)): p.read_bytes()
        for p in (output / "pilot-results").rglob("*")
        if p.is_file()
    }
    for filename in ("index.html", "index.en.html", "runs.html", "runs.en.html"):
        text = (output / filename).read_text(encoding="utf-8")
        assert 'id="project-score-table"' in text
        assert "<td>50.0</td>" in text and "<td>70.0</td>" in text
        assert "C:/private" not in text
    assert "verified-run" in (output / "runs.html").read_text(encoding="utf-8")


def test_downloads_and_approved_sources_are_preserved(tmp_path):
    from learning.proposal import PROPOSAL_ROOT

    names = (
        "proposal.pdf",
        "proposal_zh.pdf",
        "proposal_short.pdf",
        "proposal_short_zh.pdf",
    )
    before = {
        name: sha256((PROPOSAL_ROOT / name).read_bytes()).hexdigest() for name in names
    }
    write_report(tmp_path, {"status": "completed"})
    for name in names:
        assert (
            sha256((tmp_path / "proposal" / name).read_bytes()).hexdigest()
            == before[name]
        )
        for page in (
            "documents.html",
            "documents.en.html",
            "index.html",
            "index.en.html",
        ):
            assert f'href="proposal/{name}"' in (tmp_path / page).read_text(
                encoding="utf-8"
            )


def test_existing_project_and_handbook_pages_are_backed_up(tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    for name in (*PAGES, *HANDBOOK_PAGES):
        (tmp_path / name).write_text("OLD " + name)
    refresh_report(tmp_path)
    for name in (*PAGES, *HANDBOOK_PAGES):
        old = list(tmp_path.glob(name[:-5] + ".before-refresh-*.html"))
        assert len(old) == 1
        assert old[0].read_text() == "OLD " + name
