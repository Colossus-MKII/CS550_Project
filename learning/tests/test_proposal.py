from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from learning import proposal
from learning.report import write_report


def test_bilingual_snapshots_match_authoritative_files(tmp_path):
    pages = proposal.prepare_proposals(tmp_path)
    manifest = json.loads((tmp_path / "proposal/manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 8
    for name, details in manifest["files"].items():
        original = (proposal.PROPOSAL_ROOT / name).read_bytes()
        assert (tmp_path / "proposal" / details["snapshot"]).read_bytes() == original
        assert details["sha256"] == sha256(original).hexdigest()
        assert details["bytes"] == len(original)
    for language, (markdown, _) in proposal.FILES.items():
        text = (proposal.PROPOSAL_ROOT / markdown).read_text(encoding="utf-8-sig")
        assert pages[language]["html"] == proposal.render_markdown(text)
        # Abstract, five numbered sections and references; no obsolete Section 6.
        assert pages[language]["html"].count("<h4>") == 7
        assert "<h4>6 " not in pages[language]["html"]
        short_markdown, short_pdf = proposal.SHORT_FILES[language]
        assert pages[language]["short_pdf"] == "proposal/" + short_pdf
        assert pages[language]["short_source"] == "proposal/" + short_markdown + ".txt"
        assert pages[language]["short_pdf_bytes"] == (proposal.PROPOSAL_ROOT / short_pdf).stat().st_size


def test_inline_and_block_markdown_is_safe_and_complete():
    rendered = proposal.render_markdown(
        '# Title\n\n**Authors**  \nUniversity\n\n## Abstract\n\n'
        'A <script>bad()</script> & B `code` [source](https://example.org/?x=1&y=2).\n\n'
        '| Group | Weight |\n| --- | --- |\n| A0 | Pretrained |\n'
    )
    assert "<h3>Title</h3>" in rendered
    assert "<strong>Authors</strong><br>" in rendered
    assert "<h4>Abstract</h4>" in rendered
    assert "&lt;script&gt;bad()&lt;/script&gt; &amp; B <code>code</code>" in rendered
    assert 'href="https://example.org/?x=1&amp;y=2"' in rendered
    assert '<th scope="col">Group</th>' in rendered
    assert "<td>A0</td>" in rendered
    assert '<a href="javascript:' not in proposal.inline('[bad](javascript:alert(1))')


def test_review_subheadings_and_lists_render_without_raw_markdown():
    rendered = proposal.render_markdown(
        '### Controlled branches\n\n- **H:** retain history\n- **R:** reset state\n\n'
        '1. Correct once\n2. Continue normal observations\n\nFinal paragraph.\n'
    )
    assert '<h5>Controlled branches</h5>' in rendered
    assert '<ul>\n<li><strong>H:</strong> retain history</li>' in rendered
    assert '<ol>\n<li>Correct once</li>\n<li>Continue normal observations</li>' in rendered
    assert rendered.endswith('<p>Final paragraph.</p>')


def test_proposal_build_preserves_abstract_lists_table_and_citations(tmp_path):
    from tools.build_proposal import build_latex

    generated = tmp_path / 'proposal.tex'
    build_latex(proposal.PROPOSAL_ROOT / 'proposal.md', generated)
    latex = generated.read_text(encoding='utf-8')
    assert latex.count('\\begin{abstract}') == latex.count('\\end{abstract}') == 1
    assert latex.index('With model weights fixed') < latex.index('\\end{abstract}')
    assert latex.count('\\section{') == 5
    assert latex.count('\\subsection{') == 7
    assert '\\begin{itemize}' in latex and '\\begin{enumerate}' in latex
    assert '\\textbf{RQ1:' in latex
    assert '\\begin{tabularx}{\\linewidth}' in latex
    for group in ('A-H', 'A-R', 'B-H', 'B-R'):
        assert group + ' &' in latex
    for key in ('cao2023', 'ding2025', 'ravi2024', 'yang2024'):
        assert '\\citep{' + key + '}' in latex
    assert '###' not in latex and '**' not in latex


def test_bilingual_proposal_has_four_branches_and_requested_sentence_removed():
    for language, (markdown, _) in proposal.FILES.items():
        source = (proposal.PROPOSAL_ROOT / markdown).read_text(encoding='utf-8-sig')
        rendered = proposal.render_markdown(source)
        for group in ('A-H', 'A-R', 'B-H', 'B-R'):
            assert '<td>' + group + '</td>' in rendered
        for count in ('200', '120', '40', '550'):
            assert count in source
        assert rendered.count('<h5>') == 7
        assert '教学视频不参与定量评估' not in source
        assert '上游预训练数据重叠可能未知' not in source
        assert 'upstream pretraining overlap may be unknown' not in source


def test_missing_source_fails_before_writing_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(proposal, "PROPOSAL_ROOT", tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        proposal.prepare_proposals(tmp_path)
    assert not (tmp_path / "proposal").exists()


def test_missing_concise_source_does_not_partially_refresh_full_edition(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    for edition in (proposal.FILES, proposal.SHORT_FILES):
        for names in edition.values():
            for name in names:
                if name != 'proposal_short_zh.pdf':
                    (source / name).write_bytes(b'fixture')
    output = tmp_path / 'output'
    output.mkdir()
    monkeypatch.setattr(proposal, 'PROPOSAL_ROOT', source)
    with pytest.raises(FileNotFoundError, match='proposal_short_zh.pdf'):
        proposal.prepare_proposals(output)
    assert not (output / 'proposal').exists()


def test_only_explicit_proposal_sources_are_copied(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    for edition in (proposal.FILES, proposal.SHORT_FILES):
        for names in edition.values():
            for name in names:
                (source / name).write_bytes(b"# Example\n" if name.endswith(".md") else b"%PDF-example")
    for name in set(proposal.LATEX_FILES + proposal.SHORT_LATEX_FILES):
        (source / name).write_bytes(b"Local LaTeX fixture\n")
    template = tmp_path / "template"
    template.mkdir()
    for name in proposal.TEMPLATE_FILES:
        (template / name).write_bytes(b"Retained template fixture\n")
    (source / "unrelated.txt").write_text("not part of the proposal", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(proposal, "PROPOSAL_ROOT", source)
    monkeypatch.setattr(proposal, "TEMPLATE_ROOT", template)
    proposal.prepare_proposals(output)
    assert {path.name for path in (output / "proposal").iterdir()} == {
        "manifest.json", "neurips-2026-template-files.zip", "proposal-latex.zip", "proposal-short-latex.zip",
        "proposal.md.txt", "proposal.pdf", "proposal.tex", "proposal_zh.md.txt", "proposal_zh.pdf",
        "proposal_short.md.txt", "proposal_short.pdf", "proposal_short.tex",
        "proposal_short_zh.md.txt", "proposal_short_zh.pdf",
    }


def test_latex_bundles_preserve_exact_curated_sources_and_are_repeatable(tmp_path):
    downloads = proposal.latex_downloads()
    repeated = proposal.latex_downloads()
    for archive_name, root, names in (
        ("proposal-latex.zip", proposal.PROPOSAL_ROOT, proposal.LATEX_FILES),
        ("proposal-short-latex.zip", proposal.PROPOSAL_ROOT, proposal.SHORT_LATEX_FILES),
        ("neurips-2026-template-files.zip", proposal.TEMPLATE_ROOT, proposal.TEMPLATE_FILES),
    ):
        item = downloads[archive_name]
        assert item["data"] == repeated[archive_name]["data"]
        with ZipFile(BytesIO(item["data"])) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(names)
            for name in names:
                original = (root / name).read_bytes()
                assert archive.read(name) == original
                assert item["members"][name]["sha256"] == sha256(original).hexdigest()
    assert downloads["proposal.tex"]["data"] == (proposal.PROPOSAL_ROOT / "proposal.tex").read_bytes()
    assert downloads["proposal_short.tex"]["data"] == (proposal.PROPOSAL_ROOT / "proposal_short.tex").read_bytes()
    assert downloads["proposal-short-latex.zip"]["main_file"] == "proposal_short.tex"
    assert downloads["proposal-short-latex.zip"]["kind"] == "concise-proposal"
    assert downloads["neurips-2026-template-files.zip"]["kind"] == "retained-template-files-repacked"
    proposal.prepare_proposals(tmp_path)
    manifest = json.loads((tmp_path / "proposal/manifest.json").read_text(encoding="utf-8"))
    for name, item in downloads.items():
        assert (tmp_path / "proposal" / name).read_bytes() == item["data"]
        assert manifest["downloads"][name]["bytes"] == len(item["data"])
        assert manifest["downloads"][name]["sha256"] == sha256(item["data"]).hexdigest()


def test_retained_style_matches_record_after_line_ending_normalization():
    retained = (proposal.TEMPLATE_ROOT / "neurips_2026.sty").read_bytes()
    assert retained == (proposal.PROPOSAL_ROOT / "neurips_2026.sty").read_bytes()
    assert sha256(retained.replace(b"\r\n", b"\n")).hexdigest() == (
        "c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a"
    )


def test_full_text_and_revised_conditions_are_in_both_pages(tmp_path):
    write_report(tmp_path, {"status": "completed"})
    for language, filename in (("zh", "handbook.html"), ("en", "handbook.en.html")):
        html = (tmp_path / filename).read_text(encoding="utf-8")
        markdown, pdf = proposal.FILES[language]
        source = (proposal.PROPOSAL_ROOT / markdown).read_text(encoding="utf-8-sig")
        expected = proposal.render_markdown(source)
        assert f'<article id="proposal-content" class="proposal-document">{expected}</article>' in html
        assert f'href="proposal/{pdf}"' in html
        assert sha256((proposal.PROPOSAL_ROOT / markdown).read_bytes()).hexdigest() in html
        for group in ("A0", "B0"):
            assert f"<td>{group}</td>" in html
        assert "<td>A1</td>" not in html
        assert "<td>B1</td>" not in html
        assert "OPTIONAL C" not in html
        assert 'class="pipeline-label">可选 C<' not in html
        assert "reserved for optional fine-tuning" not in html
        assert "前 120 段仅为可选微调预留" not in html
        assert 'href="proposal/proposal-latex.zip" download' in html
        assert 'href="proposal/proposal.tex" download' in html
        assert 'href="proposal/neurips-2026-template-files.zip" download' in html
        assert 'id="proposal-short"' in html
        assert 'href="proposal/proposal-short-latex.zip" download' in html
        assert 'href="proposal/proposal_short.tex" download' in html
        assert 'href="proposal/proposal_short.pdf"' in html
        assert 'href="proposal/proposal_short_zh.pdf"' in html
        assert 'href="proposal/proposal_short.md.txt" download' in html
        assert 'href="proposal/proposal_short_zh.md.txt" download' in html


def test_concise_latex_separates_references_and_preserves_structure(tmp_path):
    from tools.build_proposal import build_latex

    generated = tmp_path / 'proposal_short.tex'
    build_latex(proposal.PROPOSAL_ROOT / 'proposal_short.md', generated, natural_spacing=True)
    latex = generated.read_text(encoding='utf-8')
    assert latex.count('\\clearpage') == 1  # References only, never manual body-page balancing.
    assert '\\raggedbottom' in latex
    assert latex.count('\\begin{abstract}') == latex.count('\\end{abstract}') == 1
    assert latex.count('\\section{') == 5
    assert '\\bibliography{references}' in latex
    assert '\\begin{itemize}' in latex
    assert '\\textbf{RQ1:' in latex
    assert latex.count('\\subsection{') >= 3
    assert '\\begin{tabularx}{\\linewidth}' in latex
    for group in ('A-H', 'A-R', 'B-H', 'B-R'):
        assert group + ' &' in latex
    for compressed_template in ('\\geometry{', '\\setstretch{', '\\linespread{', '\\fontsize{', '\\vspace{-', '\\addtolength{\\textheight}'):
        assert compressed_template not in latex
