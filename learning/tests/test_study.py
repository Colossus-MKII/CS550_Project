"""The advanced reference is separate, bilingual and usable without a network."""
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from learning.report import write_report
from learning.study import EVAL_REV, PAGES, SAM_REV


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.sources, self.lang = [], [], [], None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if "src" in attrs:
            self.sources.append(attrs["src"])
        if tag == "html":
            self.lang = attrs.get("lang")


def test_references_are_bilingual_static_and_versioned(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for name in PAGES:
        text = (tmp_path / name).read_text(encoding="utf-8")
        parsed = Page(text)
        assert len(parsed.ids) == len(set(parsed.ids))
        assert "@@" not in text
        assert not parsed.sources  # All styling, formulas and small scripts are embedded.
        assert SAM_REV in text and EVAL_REV in text and "v8.3.221" in text
        assert 'id="language-toggle"' in text
        if ".en." in name:
            assert parsed.lang == "en"
            visible = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', text, flags=re.S)
            visible = re.sub(r'<[^>]+>', '', visible).replace("中文", "")
            assert not re.search(r'[\u4e00-\u9fff]', visible)
        if name.startswith("math"):
            formulas = re.findall(r'<math\b.*?</math>', text, flags=re.S)
            assert len(formulas) >= 30
            for formula in formulas:
                root = ET.fromstring(formula)
                semantics = list(root)
                assert len(semantics) == 1 and semantics[0].tag.endswith("semantics")
                assert len(list(semantics[0])) == 2  # Presentation + original TeX.
    for stem in ("math", "research", "experiments"):
        zh, en = [(tmp_path / f"{stem}{suffix}.html").read_text(encoding="utf-8") for suffix in ("", ".en")]
        assert Page(zh).ids == Page(en).ids
        assert re.findall(r'<math\b.*?</math>', zh, re.S) == re.findall(r'<math\b.*?</math>', en, re.S)


def test_learning_order_and_every_local_reference_target(tmp_path):
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "environment.txt").write_text("test fixture", encoding="utf-8")
    for log in ("yolo_records.jsonl", "sam2_records.jsonl"):
        (tmp_path / log).write_text("", encoding="utf-8")
    write_report(tmp_path, {"status": "completed"})
    for name in ("handbook.html", "handbook.en.html", *PAGES):
        text = (tmp_path / name).read_text(encoding="utf-8")
        page = Page(text)
        for href in page.links:
            target = urlsplit(href)
            if target.scheme or target.netloc:
                assert target.scheme == "https"
                continue
            filename = unquote(target.path) or name
            path = tmp_path / filename
            assert path.is_file(), (name, href)
            if target.fragment:
                assert unquote(target.fragment) in Page(path.read_text(encoding="utf-8")).ids, (name, href)
        if name.startswith("handbook"):
            order = [page.ids.index(key) for key in ("overview", "chapter-1", "chapter-2", "chapter-3", "chapter-4", "chapter-6", "chapter-7", "deep-study", "proposal", "evidence", "chapter-5", "run-record")]
            assert order == sorted(order)
            assert "model-roles" in page.ids and "learning-route" in page.ids
            assert page.ids.index("start-learning-link") < page.ids.index("learning-route")
            experiment_page = "experiments.en.html" if name == "handbook.en.html" else "experiments.html"
            assert f'id="experiment-quick-link" href="{experiment_page}"' in text
            assert f'href="{experiment_page}"' in text
            assert 'id="start-learning-link" class="button primary" href="#chapter-1"' in text
            assert 'href="#chapter-7"' in text
            assert text.count('class="nav-group"') == 4
            assert '<math' not in text  # Deep formulas do not inflate the video-first main page.


def test_every_reference_section_has_a_local_outline_entry(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for name in PAGES:
        text = (tmp_path / name).read_text(encoding="utf-8")
        body = re.search(r"<main\b[^>]*>(.*?)</main>", text, re.S)[1]
        outline = re.search(r'<nav id="course-nav">(.*?)</nav>', text, re.S)[1]
        sections = set(re.findall(r'<section\b[^>]*\bid="([^"]+)"', body))
        destinations = set(re.findall(r'href="#([^"]+)"', outline))
        assert sections <= destinations, (name, sections - destinations)


def test_refresh_backs_up_existing_reference_pages(tmp_path):
    import json
    from learning.report import refresh_report

    (tmp_path / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    for name in PAGES:
        (tmp_path / name).write_text("OLD " + name, encoding="utf-8")
    refresh_report(tmp_path)
    for name in PAGES:
        stem = name.removesuffix(".html")
        backups = list(tmp_path.glob(stem + ".before-refresh-*.html"))
        assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "OLD " + name
