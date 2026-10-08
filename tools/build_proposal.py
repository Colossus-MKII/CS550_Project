#!/usr/bin/env python3
"""Build ACL LaTeX source and an editable Word companion from proposal.md.

The exact user-supplied ACL style and bibliography files compile the PDF.
The Word document is an editable approximation of its two-column layout.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from docx.opc.constants import RELATIONSHIP_TYPE


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def add_text(paragraph, text: str) -> None:
    """Preserve source links as black, unadorned Word hyperlinks."""
    cursor = 0
    for match in LINK.finditer(text):
        paragraph.add_run(text[cursor : match.start()].replace("**", ""))
        rel_id = paragraph.part.relate_to(
            match.group(2), RELATIONSHIP_TYPE.HYPERLINK, is_external=True
        )
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), rel_id)
        run = OxmlElement("w:r")
        props = OxmlElement("w:rPr")
        font = OxmlElement("w:rFonts")
        font.set(qn("w:ascii"), "Times New Roman")
        font.set(qn("w:hAnsi"), "Times New Roman")
        props.append(font)
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "000000")
        props.append(color)
        size = OxmlElement("w:sz")
        size.set(qn("w:val"), "22")
        props.append(size)
        run.append(props)
        value = OxmlElement("w:t")
        value.text = match.group(1)
        run.append(value)
        hyperlink.append(run)
        paragraph._p.append(hyperlink)
        cursor = match.end()
    paragraph.add_run(text[cursor:].replace("**", ""))


def page_setup(section, columns: int = 2) -> None:
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.header_distance = Cm(1.25)
    section.footer_distance = Inches(0.25)
    cols = section._sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        section._sectPr.append(cols)
    cols.set(qn("w:num"), str(columns))
    cols.set(qn("w:space"), str(round(Cm(0.6).twips)))
    cols.set(qn("w:equalWidth"), "1")


def build(source: Path, output: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    title = lines[0].removeprefix("# ")
    author = next(line for line in lines if line.startswith("**")).strip(" *")
    document = Document()
    document.settings.odd_and_even_pages_header_footer = False
    document.sections[0].different_first_page_header_footer = False
    for name in ["Normal", "Title", "Subtitle", "Heading 1", "Heading 2"]:
        style = document.styles[name]
        style.font.name = "Times New Roman"
        # Remove template theme overrides so Word and LibreOffice use the
        # explicit conference font, and remove the default decorative title rule.
        fonts = style.element.find(qn("w:rPr")).find(qn("w:rFonts"))
        for attribute in list(fonts.attrib):
            if "theme" in attribute.lower():
                del fonts.attrib[attribute]
        properties = style.element.find(qn("w:pPr"))
        if properties is not None:
            for border in list(properties.findall(qn("w:pBdr"))):
                properties.remove(border)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(11)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        style.paragraph_format.line_spacing = Pt(13.6)
    document.styles["Title"].font.size = Pt(14.4)
    document.styles["Title"].font.bold = True
    document.styles["Title"].paragraph_format.line_spacing = Pt(16)
    document.styles["Title"].paragraph_format.space_before = Pt(9)
    document.styles["Title"].paragraph_format.space_after = Pt(14.4)
    document.styles["Heading 1"].font.size = Pt(12)
    document.styles["Heading 1"].font.bold = True
    document.styles["Heading 1"].paragraph_format.space_before = Pt(10)
    document.styles["Heading 1"].paragraph_format.space_after = Pt(7)
    document.styles["Heading 1"].paragraph_format.keep_with_next = True
    document.styles["Normal"].paragraph_format.widow_control = True
    settings = document.settings.element
    hyphen = OxmlElement("w:autoHyphenation")
    hyphen.set(qn("w:val"), "true")
    settings.append(hyphen)
    page_setup(document.sections[0], 1)
    paragraph = document.add_paragraph(title, "Title")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for index, name in enumerate(author.split(", ")):
        if index:
            paragraph.add_run(" and ")
        paragraph.add_run(name).bold = True
    for run in paragraph.runs:
        run.font.size = Pt(12)
    for text in ["Rutgers University", "CS550 Massive Data Mining, Fall 2026"]:
        paragraph = document.add_paragraph(text)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.runs[0].font.size = Pt(12)
    # Reserve an ACL-style title box; exact PDF geometry comes from acl.sty.
    paragraph.paragraph_format.space_after = Pt(52)
    section = document.add_section(WD_SECTION_START.CONTINUOUS)
    page_setup(section, 2)
    body_start = lines.index("## Abstract")
    blocks = "\n".join(lines[body_start:]).split("\n\n")
    is_abstract = False
    is_references = False
    body_paragraphs = 0
    for block in blocks:
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text.startswith("## "):
            heading = text.removeprefix("## ")
            is_abstract = heading == "Abstract"
            is_references = heading == "References"
            body_paragraphs = 0
            p = document.add_paragraph(heading, "Heading 1")
            if is_abstract:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(0)
            continue
        if text.startswith("**Keywords:**"):
            continue
        if is_references:
            for reference in block.splitlines():
                p = document.add_paragraph()
                p.paragraph_format.left_indent = Pt(11)
                p.paragraph_format.first_line_indent = Pt(-11)
                p.paragraph_format.space_after = Pt(4)
                add_text(p, reference)
        else:
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.space_after = Pt(0)
            if is_abstract:
                p.paragraph_format.left_indent = Cm(0.6)
                p.paragraph_format.right_indent = Cm(0.6)
                p.paragraph_format.line_spacing = Pt(12)
            elif body_paragraphs:
                p.paragraph_format.first_line_indent = Pt(11)
            add_text(p, text)
            body_paragraphs += 1
            if is_abstract:
                for run in p.runs:
                    run.font.size = Pt(10)
    document.core_properties.title = title
    document.core_properties.author = author
    document.core_properties.subject = "CS550 Fall 2026 final project proposal"
    document.core_properties.keywords = "YOLO, SAM 2.1, SAM-Track, MOTS, fine-tuning, robustness"
    document.core_properties.comments = "Generated from docs/proposal.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    print(output)


CITATIONS = {
    "Cheng et al., 2023": "cheng2023",
    "Luiten et al., 2020": "luiten2020",
    "Meta AI, 2026": "meta2026",
    "OpenCV, 2026": "opencv2026",
    "Ultralytics, 2026": "ultralytics2026",
    "Yang et al., 2021": "yang2021",
    "Voigtlaender et al., 2019": "voigtlaender2019",
    "Yang and Yang, 2022": "yang2022",
}


def tex_escape(text: str) -> str:
    escapes = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
               "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
               "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(escapes.get(character, character) for character in text)


def tex_text(text: str) -> str:
    tokens = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)|\([^()]+\)")
    pieces, cursor = [], 0
    for match in tokens.finditer(text):
        pieces.append(tex_escape(text[cursor:match.start()]))
        link = LINK.fullmatch(match.group())
        if link:
            pieces.append(r"\href{" + link.group(2).replace("%", r"\%") + "}{" + tex_escape(link.group(1)) + "}")
        else:
            keys = match.group()[1:-1].split("; ")
            if all(key in CITATIONS for key in keys):
                pieces.append(r"\citep{" + ",".join(CITATIONS[key] for key in keys) + "}")
            else:
                pieces.append(tex_escape(match.group()))
        cursor = match.end()
    pieces.append(tex_escape(text[cursor:]))
    return "".join(pieces)


def build_latex(source: Path, output: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    title = tex_escape(lines[0].removeprefix("# "))
    author = next(line for line in lines if line.startswith("**")).strip(" *")
    names = r" \and ".join(tex_escape(name) for name in author.split(", "))
    preamble = r"""% Generated from docs/proposal.md; rebuild with tools/build_proposal.py.
% Uses acl.sty and acl_natbib.bst unmodified from the user-supplied ACL ZIP.
\documentclass[11pt]{article}
\usepackage[final]{acl}
\usepackage{times}
\usepackage{latexsym}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
% Named class proposal; final mode follows the supplied template's option.
\title{TITLE}
\author{NAMES\\
{\normalfont Rutgers University}\\
{\normalfont CS550 Massive Data Mining, Fall 2026}}
\begin{document}
\maketitle
""".replace("TITLE", title).replace("NAMES", names)
    parts = [preamble]
    blocks = "\n".join(lines[lines.index("## Abstract"):]).split("\n\n")
    mode = ""
    for block in blocks:
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text.startswith("## "):
            heading = text.removeprefix("## ")
            if heading == "Abstract":
                mode = "abstract"
                parts.append(r"\begin{abstract}")
            elif heading == "References":
                break
            else:
                mode = "body"
                parts.append(r"\section{" + tex_escape(re.sub(r"^\d+ ", "", heading)) + "}")
        elif text.startswith("**Keywords:**"):
            continue
        else:
            parts.append(tex_text(text))
            if mode == "abstract":
                parts.append(r"\end{abstract}")
    parts.extend([r"\bibliography{references}", r"\end{document}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(output)


def build_source_zip(latex_source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    instructions = (
        "CS550 proposal using the exact user-supplied ACL conference template.\n\n"
        "Upload this ZIP to Overleaf and set proposal.tex as the main document,\n"
        "or compile with tectonic --untrusted proposal.tex.\n"
        "Standard TeX dependencies come from the compiler/TeX distribution.\n"
        "acl.sty and acl_natbib.bst are unmodified from the supplied ZIP.\n"
        "See TEMPLATE-PROVENANCE.md and LICENSE-LPPL-1.3c.txt.\n"
    )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(latex_source, "proposal.tex")
        archive.write(ROOT / "paper/references.bib", "references.bib")
        archive.write(ROOT / "templates/acl/acl.sty", "acl.sty")
        archive.write(ROOT / "templates/acl/acl_natbib.bst", "acl_natbib.bst")
        archive.write(ROOT / "templates/acl/LICENSE-LPPL-1.3c.txt", "LICENSE-LPPL-1.3c.txt")
        archive.write(ROOT / "templates/acl/README.md", "TEMPLATE-PROVENANCE.md")
        archive.writestr("README.txt", instructions)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/proposal.md")
    parser.add_argument("--output", type=Path, default=ROOT / "output/docx/proposal.docx")
    parser.add_argument("--latex-output", type=Path, default=ROOT / "paper/proposal.tex")
    parser.add_argument("--source-zip", type=Path, default=ROOT / "output/latex/proposal_acl_source.zip")
    args = parser.parse_args()
    build(args.source, args.output)
    build_latex(args.source, args.latex_output)
    build_source_zip(args.latex_output, args.source_zip)
