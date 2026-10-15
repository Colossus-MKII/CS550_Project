#!/usr/bin/env python3
"""Build a readable Chinese review PDF from proposal_zh.md.

Requires ReportLab and embeddable CJK TrueType fonts. The English submission
continues to use the unchanged NeurIPS template through build_proposal.py.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import textsplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import paragraph as paragraph_module


ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#202A35")
ACCENT = colors.HexColor("#204B67")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def inline(text: str) -> str:
    parts, cursor = [], 0
    tokens = re.compile(r"\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^)]+)\)")
    for match in tokens.finditer(text):
        parts.append(escape(text[cursor:match.start()]))
        strong, code, label, url = match.groups()
        if strong is not None:
            parts.append('<b>' + escape(strong) + '</b>')
        elif code is not None:
            parts.append(escape(code))
        else:
            parts.append('<link href="' + escape(url, {'"': '&quot;'})
                         + '" color="#204B67">' + escape(label) + '</link>')
        cursor = match.end()
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def page_frame(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CCD6DF"))
    canvas.setLineWidth(0.5)
    canvas.line(52, 42, width - 52, 42)
    canvas.setFont("ReviewRegular", 8)
    canvas.setFillColor(colors.HexColor("#647282"))
    canvas.drawString(52, 29, "CS550 项目提案 | 中文审阅版")
    canvas.drawRightString(width - 52, 29, str(doc.page))
    if doc.page > 1:
        canvas.drawString(52, height - 31, doc.title)
    canvas.restoreState()


def build(source: Path, output: Path, regular: Path, bold: Path, *, separate_references: bool = True) -> None:
    # ReportLab's default CJK prohibition list omits some Chinese punctuation.
    # Add it in both line-breaking paths to avoid punctuation at line starts.
    for module in (textsplit, paragraph_module):
        module.ALL_CANNOT_START += "，；：！？）》】”’"
    pdfmetrics.registerFont(TTFont("ReviewRegular", str(regular)))
    pdfmetrics.registerFont(TTFont("ReviewBold", str(bold)))
    pdfmetrics.registerFontFamily("ReviewRegular", normal="ReviewRegular", bold="ReviewBold")
    body = ParagraphStyle(
        "Body", fontName="ReviewRegular", fontSize=10.2, leading=16.2,
        textColor=INK, alignment=TA_LEFT, wordWrap="CJK", spaceAfter=6,
        allowWidows=0, allowOrphans=0,
    )
    heading = ParagraphStyle(
        "Heading", parent=body, fontName="ReviewBold", fontSize=11.5,
        leading=17, spaceBefore=9, spaceAfter=5, keepWithNext=True,
        textColor=ACCENT,
    )
    subheading = ParagraphStyle("Subheading", parent=heading, fontSize=10.5,
                                leading=16, spaceBefore=7, spaceAfter=4)
    list_item = ParagraphStyle("ListItem", parent=body, leftIndent=14,
                              firstLineIndent=0, bulletIndent=0, spaceAfter=3)
    table_body = ParagraphStyle("TableBody", parent=body, fontSize=9.5,
                                leading=14, spaceAfter=0)
    title = ParagraphStyle(
        "Title", parent=body, fontName="ReviewBold", fontSize=18,
        leading=27, spaceAfter=9, keepWithNext=True,
    )
    meta = ParagraphStyle("Meta", parent=body, fontSize=9, leading=14,
                          textColor=colors.HexColor("#596878"), spaceAfter=5)
    reference = ParagraphStyle("Reference", parent=body, fontName="Times-Roman",
                               fontSize=10, leading=14, wordWrap=None, spaceAfter=11)
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    in_body = False
    in_references = False
    for block in "\n".join(lines).split("\n\n"):
        if block.strip() == "<!-- pagebreak -->":
            story.append(PageBreak())
            continue
        if block.lstrip().startswith("|"):
            rows = []
            for line in block.splitlines():
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    continue
                if len(cells) != 3:
                    raise ValueError("Proposal tables must have exactly three columns")
                rows.append([Paragraph(inline(cell), table_body) for cell in cells])
            table = Table(rows, colWidths=[64, 145, A4[0] - 104 - 209], repeatRows=1,
                          hAlign="LEFT", spaceBefore=3, spaceAfter=10, splitByRow=0)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0F4")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, ACCENT),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(table)
            continue
        list_lines = block.strip().splitlines()
        if list_lines and all(re.match(r"^(?:- |\d+\. )", line) for line in list_lines):
            for line in list_lines:
                match = re.match(r"^(-|\d+\.) (.+)$", line)
                bullet = "•" if match[1] == "-" else match[1]
                story.append(Paragraph(inline(match[2]), list_item, bulletText=bullet))
            continue
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text.startswith("# "):
            story.append(Paragraph(inline(text[2:]), title))
        elif text.startswith("### "):
            story.append(Paragraph(inline(text[4:]), subheading))
        elif text.startswith("## "):
            label = text[3:]
            if label == "参考文献" and separate_references:
                story.append(PageBreak())
            in_body = True
            in_references = label == "参考文献"
            story.append(Paragraph(inline(label), heading))
        elif text.startswith("**") and not in_body:
            story.append(Paragraph(inline(text.strip(" *")), meta))
        elif not in_body:
            story.append(Paragraph("<br/>".join(inline(line.strip()) for line in block.splitlines()), meta))
            story.append(Spacer(1, 3))
        else:
            story.append(Paragraph(inline(text), reference if in_references else body))
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=A4, leftMargin=52, rightMargin=52,
        topMargin=48, bottomMargin=55,
        title=lines[0].removeprefix("# "),
        author="Jingdi Wu, Yupu Guo, Christina Ross",
        subject="CS550 revised project proposal, Chinese review version",
    )
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/proposal/proposal_zh.md")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/proposal/proposal_zh.pdf")
    parser.add_argument("--font-regular", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"))
    parser.add_argument("--font-bold", type=Path, default=Path("C:/Windows/Fonts/msyhbd.ttc"))
    parser.add_argument("--inline-references", action="store_true",
                        help="Keep references in the normal flow for the concise edition.")
    args = parser.parse_args()
    build(args.source, args.output, args.font_regular, args.font_bold,
          separate_references=not args.inline_references)
