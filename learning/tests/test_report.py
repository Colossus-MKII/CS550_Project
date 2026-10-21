import json
import re
from html.parser import HTMLParser

from learning.report import WEB, refresh_report, write_report


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "src" in attrs:
            self.sources.append(attrs["src"])


def test_full_curriculum_and_unique_ids(tmp_path):
    write_report(tmp_path, {"status": "failed"})
    html = (tmp_path / "handbook.html").read_text(encoding="utf-8")
    parsed = Elements()
    parsed.feed(html)
    assert len(parsed.ids) == len(set(parsed.ids))
    assert all(f"chapter-{i}" in parsed.ids for i in range(1, 8))
    for text in ["ultralytics", "卡尔曼", "叼球", "DeAOT", "IDF1", "HOTA", "Ground Truth"]:
        assert text in html
    assert "@@" not in html
    assert 'id="frame-explorer" hidden' in html
    assert not any(src.startswith(("https:", "http:")) for src in parsed.sources)
    assert (tmp_path / "code/yolo_lessons.py.txt").read_text(encoding="utf-8").startswith('"""Lessons')


def test_records_are_embedded_safely_and_frames_are_real(tmp_path):
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames/00000.jpg").write_bytes(b"placeholder")
    (tmp_path / "yolo_records.jsonl").write_text(
        json.dumps({"frame": 0, "detections": [{"class_name": "</script><script>oops()</script>"}], "tracks": []}),
        encoding="utf-8",
    )
    write_report(tmp_path, {"status": "completed", "clip": {"frames": 3, "fps": 12}})
    html = (tmp_path / "handbook.html").read_text(encoding="utf-8")
    payload = html.split('<script id="lesson-data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(payload)
    assert data["frames"] == [0]
    assert data["fps"] == 12
    assert data["yolo"][0]["detections"][0]["class_name"] == "</script><script>oops()</script>"
    assert "<script>oops()" not in html


def test_malformed_optional_log_is_disclosed(tmp_path):
    (tmp_path / "sam2_records.jsonl").write_text("{broken", encoding="utf-8")
    write_report(tmp_path, {"status": "partial", "clip": {"fps": float("nan")}})
    html = (tmp_path / "handbook.html").read_text(encoding="utf-8")
    assert "无法完整读取" in html
    assert '"fps": 30' in html


def test_refresh_preserves_previous_page_and_measurements(tmp_path):
    summary = {"status": "completed", "source": "local-demo.mp4"}
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    original_summary = (tmp_path / "summary.json").read_bytes()
    (tmp_path / "index.html").write_text("OLD PAGE", encoding="utf-8")
    (tmp_path / "index.en.html").write_text("OLD ENGLISH PAGE", encoding="utf-8")
    (tmp_path / "comparison.mp4").write_bytes(b"ORIGINAL VIDEO")
    (tmp_path / "yolo_records.jsonl").write_text('{"frame":0,"tracks":[]}', encoding="utf-8")
    backup = refresh_report(tmp_path)
    assert backup.read_text(encoding="utf-8") == "OLD PAGE"
    english_backups = list(tmp_path.glob("index.en.before-refresh-*.html"))
    assert len(english_backups) == 1
    assert english_backups[0].read_text(encoding="utf-8") == "OLD ENGLISH PAGE"
    assert (tmp_path / "summary.json").read_bytes() == original_summary
    assert (tmp_path / "comparison.mp4").read_bytes() == b"ORIGINAL VIDEO"
    assert (tmp_path / "yolo_records.jsonl").read_text(encoding="utf-8") == '{"frame":0,"tracks":[]}'
    assert 'id="video-comparison"' in (tmp_path / "handbook.html").read_text(encoding="utf-8")
    assert 'id="latest-results-link"' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_bilingual_pages_share_structure_code_and_measurements(tmp_path):
    (tmp_path / "comparison.mp4").write_bytes(b"VIDEO")
    (tmp_path / "sam2_prompt.jpg").write_bytes(b"IMAGE")
    (tmp_path / "sam2_prompts.json").write_text("[]", encoding="utf-8")
    (tmp_path / "yolo_records.jsonl").write_text('{"frame":0,"tracks":[]}', encoding="utf-8")
    write_report(tmp_path, {"status": "completed", "clip": {"frames": 1}})
    pages = [(tmp_path / filename).read_text(encoding="utf-8") for filename in ("handbook.html", "handbook.en.html")]
    structures = []
    payloads = []
    for html, language in zip(pages, ("zh", "en")):
        parsed = Elements()
        parsed.feed(html)
        assert len(parsed.ids) == len(set(parsed.ids))
        structures.append(parsed.ids)
        assert "@@" not in html
        payload = html.split('<script id="lesson-data" type="application/json">')[1].split("</script>")[0]
        data = json.loads(payload)
        assert data.pop("language") == language
        payloads.append(data)
    assert structures[0] == structures[1]
    assert payloads[0] == payloads[1]
    # Actual source excerpts are not translated or modified.
    snippets = [re.findall(r'<code id="code-[^"]+">(.*?)</code>', page, re.S) for page in pages]
    assert snippets[0] == snippets[1]
    assert 'id="language-toggle" href="handbook.en.html"' in pages[0]
    assert 'id="language-toggle" href="handbook.html"' in pages[1]
    assert '<html lang="en">' in pages[1]
    for phrase in ("Kalman", "ultralytics", "throw ball", "visual memory", "not ground", "SYNTHETIC LAB", "Original dimensions", "Copy code", "No source frames", "View coordinates"):
        assert phrase in pages[1]
    # No untranslated Chinese prose in the English template; the language link is intentional.
    visible = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', pages[1], flags=re.S)
    visible = re.sub(r'<[^>]+>', '', visible).replace("中文", "")
    assert not re.search(r'[\u4e00-\u9fff]', visible)


def test_english_optional_log_warning(tmp_path):
    (tmp_path / "sam2_records.jsonl").write_text("{broken", encoding="utf-8")
    write_report(tmp_path, {"status": "partial"})
    english = (tmp_path / "handbook.en.html").read_text(encoding="utf-8")
    assert "Could not fully read sam2_records.jsonl" in english


def test_project_document_copy_preserves_technical_content(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for filename, heading, removed_slogan in (
        ("handbook.html", "目标检测、分割与跟踪", "从一个框"),
        ("handbook.en.html", "Detection, Segmentation and Tracking", "From a box"),
    ):
        page = (tmp_path / filename).read_text(encoding="utf-8")
        assert f"<h1>{heading}</h1>" in page
        assert removed_slogan not in page
        for old_markup in ('class="sidebar-note"', 'class="concept-strip"',
                           'class="chapter-question"', '<p class="takeaway">'):
            assert old_markup not in page
        assert page.count('data-complete="chapter-') == 7
        assert page.count('class="formula"') == 3
        for technical_term in ("yolo11s-seg.pt", "persist=True", "retina_masks=True",
                               "logits", "IDTP", "AssA", "AP50:95", "120", "40",
                               "proposal-latex.zip", "neurips-2026-template-files.zip"):
            assert technical_term in page


def test_bilingual_favicons_are_local_and_copied(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for filename in ("favicon.svg", "favicon-32.png", "favicon.ico"):
        assert (tmp_path / filename).read_bytes() == (WEB / filename).read_bytes()
        for page in ("index.html", "index.en.html", "handbook.html", "handbook.en.html"):
            assert f'href="{filename}?v=1"' in (tmp_path / page).read_text(encoding="utf-8")
    png = (tmp_path / "favicon-32.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert int.from_bytes(png[16:20], "big") == 32
    assert int.from_bytes(png[20:24], "big") == 32
    ico = (tmp_path / "favicon.ico").read_bytes()
    assert ico[:6] == b"\x00\x00\x01\x00\x03\x00"
    for index, size in enumerate((16, 32, 48)):
        entry = 6 + index * 16
        assert ico[entry] == ico[entry + 1] == size
        offset = int.from_bytes(ico[entry + 12:entry + 16], "little")
        assert ico[offset:offset + 8] == b"\x89PNG\r\n\x1a\n"
