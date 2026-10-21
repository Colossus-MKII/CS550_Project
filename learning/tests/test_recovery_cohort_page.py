"""Check the cohort's evidence navigation without running any models."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import os

import pytest

from learning.recovery_cohort_page import PAGES, PREFIX, write_cohort_pages

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(
    os.environ.get(
        "CS550_SITE_OUTPUT", ROOT / "outputs/learning/20261011-095748-9d89fd"
    )
)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.resources, self.videos, self.images = [], [], 0, 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "video":
            self.videos += 1
            assert a.get("preload") == "none"
        self.images += tag == "img"
        for key in ("href", "src"):
            if a.get(key):
                self.resources.append(a[key])


def test_empty_site_does_not_import_real_experiments(tmp_path):
    write_cohort_pages(tmp_path)
    assert not (tmp_path / PREFIX).exists()
    for name in PAGES:
        page = Page((tmp_path / name).read_text(encoding="utf-8"))
        assert page.videos == page.images == 0
        assert len(page.ids) == len(set(page.ids))


@pytest.mark.skipif(
    not (SITE / PREFIX / "manifest.json").is_file(),
    reason="Optional saved-cohort integration check; set CS550_SITE_OUTPUT to local results",
)
def test_actual_bilingual_cohort_and_assets():
    manifest = json.loads((SITE / PREFIX / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["main_branches"] == 128 and manifest["primary_events"] == 16
    assert not manifest["boundary_case_2967_run"]
    assert manifest["verification"] == {
        "main": "passed",
        "repeat": "passed",
        "old_results": "passed",
    }
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        page = Page(text)
        assert "@@" not in text and page.videos == 32 and page.images == 64
        assert len(page.ids) == len(set(page.ids))
        for event in range(1, 17):
            assert f"E{event:02}" in page.ids
        for ref in page.resources:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            destination = (
                (SITE / unquote(url.path)).resolve() if url.path else SITE / name
            )
            assert destination.is_relative_to(SITE.resolve())
            assert destination.is_file(), (name, ref)
            if url.fragment and destination.suffix == ".html":
                assert (
                    unquote(url.fragment)
                    in Page(destination.read_text(encoding="utf-8")).ids
                ), (name, ref)
        home = (SITE / ("index.en.html" if ".en." in name else "index.html")).read_text(
            encoding="utf-8"
        )
        assert f'id="latest-results-link" class="button primary" href="{name}"' in home
