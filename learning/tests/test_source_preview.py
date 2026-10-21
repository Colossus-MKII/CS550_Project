import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import pytest

from learning.preview import build_preview


class References(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids, self.links = [], []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])


def test_source_preview_builds_without_model_runtime_or_saved_results(tmp_path):
    output = tmp_path / "source-preview"
    script = """
import importlib.abc
from pathlib import Path
import sys
class NoInference(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'ultralytics', 'sam2', 'tracking_lab'}:
            raise AssertionError('Preview tried to import model runtime: ' + fullname)
sys.meta_path.insert(0, NoInference())
from learning.preview import build_preview
build_preview(Path(sys.argv[1]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(output)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((output / "summary.json").read_text())["preview_only"]
    families = (
        "index",
        "runs",
        "documents",
        "handbook",
        "math",
        "research",
        "experiments",
        "program",
        "dataset",
        "results",
        "recovery",
        "recovery-long",
        "recovery-cohort",
    )
    for slug in families:
        for suffix in ("", ".en"):
            text = (output / f"{slug}{suffix}.html").read_text(encoding="utf-8")
            assert 'id="language-toggle"' in text and 'id="course-nav"' in text
            assert "@@" not in text
    assert not any(output.rglob("*.mp4"))
    for folder in (
        "pilot-results",
        "dataset-samples",
        "recovery-results",
        "recovery-long-results",
        "recovery-cohort-results",
    ):
        assert not (output / folder).exists()
    pages = {path.resolve(): References(path) for path in output.rglob("*.html")}
    for path, page in pages.items():
        assert len(page.ids) == len(set(page.ids)), path
        for link in page.links:
            target = urlsplit(link)
            if target.scheme or target.netloc:
                continue
            destination = (
                (path.parent / unquote(target.path)).resolve() if target.path else path
            )
            assert destination.is_relative_to(output.resolve()), (path, link)
            assert destination.is_file(), (path, link)
            if target.fragment and destination.suffix == ".html":
                assert unquote(target.fragment) in pages[destination].ids, (path, link)


def test_preview_refuses_to_change_an_existing_run(tmp_path):
    output = tmp_path / "existing-run"
    output.mkdir()
    original = b'{"status":"completed","measurement":0.75}'
    (output / "summary.json").write_bytes(original)
    with pytest.raises(FileExistsError, match="already exists"):
        build_preview(output)
    assert (output / "summary.json").read_bytes() == original
    assert [p.name for p in output.iterdir()] == ["summary.json"]
