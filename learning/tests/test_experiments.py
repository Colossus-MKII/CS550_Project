"""Protocol content stays paired, bilingual, local and explicit about its status."""
import re

from learning.study import write_study_pages
from learning.tests.test_study import Page


def test_protocol_structure_and_no_script_readability(tmp_path):
    write_study_pages(tmp_path)
    structures = []
    for suffix, language in (("", "zh-CN"), (".en", "en")):
        html = (tmp_path / f"experiments{suffix}.html").read_text(encoding="utf-8")
        parsed = Page(html)
        assert parsed.lang == language
        assert len(parsed.ids) == len(set(parsed.ids))
        structures.append(parsed.ids)
        assert not parsed.sources
        assert "@@" not in html
        assert html.count('data-event-panel="') == 5
        assert html.count('data-event-step="') == 5
        assert 'id="event-controls" hidden' in html
        # Without JavaScript every explanatory panel is visible, in order.
        panels = re.findall(r'<article\b([^>]*)>', html)
        assert len(panels) == 5
        assert all('hidden' not in attrs for attrs in panels)
        assert all(f'id="event-heading-{i}"' in html for i in range(5))
        matrix = html.split('id="recovery-groups"')[1].split('</table>')[0]
        assert matrix.count('<tbody>') == 1 and matrix.count('<tr>') == 5
        assert all(group in matrix for group in ('A-H', 'A-R', 'B-H', 'B-R'))
        assert all(name in html for name in ('ByteTrack', 'OC-SORT', 'SAM 2', 'SAM2Long', 'SAMURAI'))
        assert 're_activate()' in html and 'clear_old_points=True' in html
        assert '200' in html and '120' in html and '550' in html
    assert structures[0] == structures[1]


def test_controls_and_causal_boundaries_are_explained(tmp_path):
    write_study_pages(tmp_path)
    english = (tmp_path / 'experiments.en.html').read_text(encoding='utf-8')
    for phrase in (
        'H receives the correction too',
        'Do not update again',
        'do not share internal state',
        'Do not fabricate a retained branch',
        'zero velocity',
        'default initial covariance',
        'preserve the external target ID',
        'no further human or annotation-based corrections',
        'continue the scheduled detection stream',
        'Exclude the directly corrected frame',
        'Visible-target misses or empty outputs count as failures',
        'actual experiments',
        'at most one automatic-policy validation',
    ):
        assert phrase.casefold() in english.casefold(), phrase
    assert 'step' in english and 'destination.searchParams.set' in english
    # No results plot or invented outcome data masquerades as evidence.
    assert '<canvas' not in english and 'data-recovery-score' not in english


def test_math_and_history_follow_the_approved_scope(tmp_path):
    write_study_pages(tmp_path)
    math = (tmp_path / 'math.en.html').read_text(encoding='utf-8')
    research = (tmp_path / 'research.en.html').read_text(encoding='utf-8')
    assert 'Core experiments' in research
    assert 'A-H/A-R and B-H/B-R' in math
    assert 'not initialization' in math
    assert 'reference boxes' in math
    assert 'SAMURAI' in research and 'OC-SORT' in research
    assert 'no-memory control' in research
    assert 'experiments.en.html' in math and 'experiments.en.html' in research
