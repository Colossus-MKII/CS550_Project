#!/usr/bin/env python3
"""Build the editable two-column proposal from docs/proposal.md.

Run with python-docx, then use the documented render_docx.py workflow to create
the matching PDF and visually check both pages. The Markdown is authoritative.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
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
        size.set(qn("w:val"), "20")
        props.append(size)
        run.append(props)
        value = OxmlElement("w:t")
        value.text = match.group(1)
        run.append(value)
        hyperlink.append(run)
        paragraph._p.append(hyperlink)
        cursor = match.end()
    paragraph.add_run(text[cursor:].replace("**", ""))


def page_setup(section, columns: int) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(1.25)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    section.header_distance = Inches(0.25)
    section.footer_distance = Inches(0.25)
    cols = section._sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        section._sectPr.append(cols)
    cols.set(qn("w:num"), str(columns))
    cols.set(qn("w:space"), "540")
    cols.set(qn("w:equalWidth"), "1")


def build(source: Path, output: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    title = lines[0].removeprefix("# ")
    author = next(line for line in lines if line.startswith("**")).strip(" *")
    document = Document()
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
        style.font.size = Pt(10)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        style.paragraph_format.line_spacing = Pt(12)
    document.styles["Title"].font.size = Pt(16)
    document.styles["Title"].font.bold = True
    document.styles["Title"].paragraph_format.line_spacing = Pt(18)
    document.styles["Title"].paragraph_format.space_after = Pt(8)
    document.styles["Heading 1"].font.size = Pt(11)
    document.styles["Heading 1"].font.bold = True
    document.styles["Heading 1"].paragraph_format.space_before = Pt(7)
    document.styles["Heading 1"].paragraph_format.space_after = Pt(3)
    document.styles["Heading 1"].paragraph_format.keep_with_next = True
    document.styles["Normal"].paragraph_format.widow_control = True
    settings = document.settings.element
    hyphen = OxmlElement("w:autoHyphenation")
    hyphen.set(qn("w:val"), "true")
    settings.append(hyphen)
    page_setup(document.sections[0], 1)
    paragraph = document.add_paragraph(title, "Title")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph = document.add_paragraph(author)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(2)
    for value in [
        "Rutgers University | CS550 Massive Data Mining | Fall 2026",
        "Project proposal | October 7 2026",
    ]:
        paragraph = document.add_paragraph(value)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in paragraph.runs:
            run.font.size = Pt(9)
    document.paragraphs[-1].paragraph_format.space_after = Pt(10)
    section = document.add_section(WD_SECTION_START.CONTINUOUS)
    page_setup(section, 2)
    body_start = lines.index("## Abstract")
    blocks = "\n".join(lines[body_start:]).split("\n\n")
    is_abstract = False
    is_references = False
    for block in blocks:
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text.startswith("## "):
            heading = text.removeprefix("## ")
            is_abstract = heading == "Abstract"
            is_references = heading == "References"
            p = document.add_paragraph(heading, "Heading 1")
            if is_abstract:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(0)
            continue
        if is_references:
            for reference in block.splitlines():
                p = document.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.16)
                p.paragraph_format.first_line_indent = Inches(-0.16)
                p.paragraph_format.space_after = Pt(2)
                add_text(p, reference)
        else:
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.space_after = Pt(3)
            if is_abstract:
                p.paragraph_format.left_indent = Inches(0.12)
                p.paragraph_format.right_indent = Inches(0.12)
            add_text(p, text)
    document.core_properties.title = title
    document.core_properties.author = author
    document.core_properties.subject = "CS550 Fall 2026 final project proposal"
    document.core_properties.keywords = "SAM 3, instance segmentation, tracking, robustness"
    document.core_properties.comments = "Generated from docs/proposal.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/proposal.md")
    parser.add_argument("--output", type=Path, default=ROOT / "output/docx/proposal.docx")
    args = parser.parse_args()
    build(args.source, args.output)
