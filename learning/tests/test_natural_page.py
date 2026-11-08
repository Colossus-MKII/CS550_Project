"""Natural-failure website import and bilingual evidence checks; no inference."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from learning.natural_page import PAGES, PREFIX, write_natural_pages

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(os.environ.get("CS550_SITE_OUTPUT", ROOT / "outputs/learning/20261011-095748-9d89fd"))


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.paths, self.videos = [], [], 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "video":
            self.videos += 1
            assert attrs.get("preload") == "none"
        self.paths.extend(attrs[k] for k in ("href", "src") if attrs.get(k))


def test_empty_site_has_no_invented_results_or_runtime_import(tmp_path):
    write_natural_pages(tmp_path)
    assert not (tmp_path / PREFIX).exists()
    for name in PAGES:
        text = (tmp_path / name).read_text(encoding="utf-8")
        page = Page(text)
        assert page.videos == 0
        assert "52 main" not in text and "52主分支" not in text
        assert len(page.ids) == len(set(page.ids))


@pytest.mark.skipif(not (SITE/PREFIX/"manifest.json").exists(), reason="Optional saved natural-failure assets absent")
def test_actual_bilingual_natural_evidence_is_sanitized_and_linked():
    raw = (SITE/PREFIX/"manifest.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert (data["events"], data["main_branches"], data["repeat_branches"], data["comparison_videos"]) == (7,52,20,13)
    assert data["history_pollution_included"] is False
    assert "D:\\" not in raw and "baseline_folder" not in raw and "samples_root" not in raw
    case = next(c for c in data["cases"] if c["key"]=="reference-S01")
    assert case["conditions"]==["reference"]
    p = next(p for p in case["pairs"] if p["model"]=="B" and p["window"]==30)
    assert [p[k]["correct_visible_steps"] for k in ("uncorrected","H","R")] == [27,30,0]
    for name in PAGES:
        text=(SITE/name).read_text(encoding="utf-8")
        page=Page(text)
        assert page.videos==13 and "@@" not in text
        assert len(page.ids)==len(set(page.ids))
        for ref in page.paths:
            url=urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            destination=(SITE/url.path) if url.path else SITE/name
            assert destination.is_file(), (name,ref)
        home=(SITE/("index.en.html" if ".en." in name else "index.html")).read_text(encoding="utf-8")
        assert f'id="latest-results-link" class="button secondary" href="{name}"' in home
        assert 'id="learning-entry-link"' in home
