from html.parser import HTMLParser
import json
from urllib.parse import urlsplit

from learning import journey
from learning.report import write_report


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs)


def test_each_language_has_one_ordered_route_and_distinct_sidebar_pages(tmp_path):
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    write_report(tmp_path, {"status": "source-preview"})
    for language in ("zh", "en"):
        home = tmp_path / journey.href("index", language)
        text = home.read_text(encoding="utf-8")
        nav = text.split('id="project-navigation"', 1)[1].split("</nav>", 1)[0]
        route = text.split('<ol class="journey-map">', 1)[1].split("</ol>", 1)[0]
        positions = [
            route.index(f'href="{journey.stage_href(stage, language)}"')
            for stage in journey.STAGES
        ]
        assert positions == sorted(positions)
        assert 'id="baseline-entry-link"' in text and 'id="latest-results-link"' in text
        assert nav.index('data-route-page="recovery"') < nav.index(
            'data-route-page="recovery-long"'
        )
        for i, stage in enumerate(journey.STAGES):
            route_target = urlsplit(journey.stage_href(stage, language))
            page = Page(tmp_path / route_target.path)
            assert not route_target.fragment or route_target.fragment in page.ids
            current = [a for a in page.links if a.get("aria-current") == "page"]
            assert [a["data-route-page"] for a in current] == [stage.page]
            following = [a["href"] for a in page.links if "data-route-next" in a]
            previous = [a["href"] for a in page.links if "data-route-prev" in a]
            assert following == (
                [journey.stage_href(journey.STAGES[i + 1], language)]
                if i + 1 < len(journey.STAGES)
                else []
            )
            assert previous == (
                [journey.stage_href(journey.STAGES[i - 1], language)] if i else []
            )


def test_missing_local_evidence_is_distinct_from_pending_formal_evaluation(
    tmp_path, monkeypatch
):
    manifest = tmp_path / "split.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "frozen_before_candidate_baseline_inference",
                "selected_video_count": 200,
                "splits": {
                    "development": [0] * 120,
                    "validation": [0] * 40,
                    "evaluation": [0] * 40,
                },
            }
        )
    )
    monkeypatch.setattr(journey, "SPLIT_MANIFEST", manifest)
    assert "120 development, 40 validation and 40 held out" in journey.split_status(
        "en"
    )
    assert journey.status(journey.BY_PAGE["runs"], tmp_path, "en")[0] == "pending"
    assert (
        journey.status(journey.BY_PAGE["recovery-natural"], tmp_path, "en")[0]
        == "unavailable"
    )
    assert journey.latest(tmp_path) is None
    saved = tmp_path / journey.BY_PAGE["recovery-long"].evidence
    saved.parent.mkdir()
    saved.write_text("{}")
    assert journey.latest(tmp_path).page == "recovery-long"
    assert journey.status(journey.BY_PAGE["recovery-long"], tmp_path, "en")[0] == "done"
