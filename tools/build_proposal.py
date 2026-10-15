#!/usr/bin/env python3
"""Build the NeurIPS LaTeX proposal from its Markdown source.

Uses only Python's standard library. The exact user-supplied NeurIPS style
compiles the PDF separately in a TeX environment.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


CITATIONS = {
    "Cao et al., 2023": "cao2023",
    "Ding et al., 2025": "ding2025",
    "Ravi et al., 2024": "ravi2024",
    "Yang et al., 2024": "yang2024",
    "Cheng et al., 2023": "cheng2023",
    "Luiten et al., 2020": "luiten2020",
    "Luiten and Hoffhues, 2020": "trackeval2020",
    "Ristani et al., 2016": "ristani2016",
    "Meta AI, 2026": "meta2026",
    "OpenCV, 2026": "opencv2026",
    "Ultralytics, 2026": "ultralytics2026",
    "Moon et al., 2026": "moon2026",
    "Voigtlaender et al., 2019": "voigtlaender2019",
    "Yang and Yang, 2022": "yang2022",
    "Zhang et al., 2021": "zhang2021",
}


def tex_escape(text: str) -> str:
    escapes = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
               "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
               "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(escapes.get(character, character) for character in text)


def tex_text(text: str) -> str:
    tokens = re.compile(r"\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?://[^)]+\)|\([^()]+\)")
    pieces, cursor = [], 0
    for match in tokens.finditer(text):
        pieces.append(tex_escape(text[cursor:match.start()]))
        link = LINK.fullmatch(match.group())
        if match.group().startswith("**"):
            pieces.append(r"\textbf{" + tex_text(match.group()[2:-2]) + "}")
        elif match.group().startswith("`"):
            pieces.append(r"\texttt{" + tex_escape(match.group()[1:-1]) + "}")
        elif link:
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


def build_latex(source: Path, output: Path, *, separate_references: bool = True,
                natural_spacing: bool = False) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    title = tex_escape(lines[0].removeprefix("# "))
    author = next(line for line in lines if line.startswith("**")).strip(" *")
    author_blocks = []
    for name in author.split(", "):
        author_blocks.append(tex_escape(name) + r"\\" + "\n" +
                             r"{\normalfont Rutgers University}")
    names = "\n\\And\n".join(author_blocks)
    preamble = r"""% CS550 project proposal.
% Uses the unchanged, user-supplied NeurIPS 2026 style.
\documentclass{article}
\usepackage[preprint]{neurips_2026}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{hyperref}
\usepackage{url}
\usepackage{microtype}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{tabularx}
\hypersetup{hidelinks}
\setcitestyle{authoryear,round}
% Named course proposal.
\title{TITLE}
\author{NAMES}
\begin{document}
\maketitle
""".replace("TITLE", title).replace("NAMES", names)
    parts = [preamble]
    if natural_spacing:
        # Keep normal paragraph spacing instead of stretching every page to
        # the same bottom edge. Font sizes and template margins stay unchanged.
        parts.append(r"\raggedbottom")
    blocks = "\n".join(lines[lines.index("## Abstract"):]).split("\n\n")
    mode = ""
    for block in blocks:
        if block.strip() == "<!-- pagebreak -->":
            parts.append(r"\clearpage")
            continue
        if block.startswith("## ") and mode == "abstract":
            parts.append(r"\end{abstract}")
            mode = "body"
        if block.lstrip().startswith("|"):
            rows = [line.strip().strip("|").split("|") for line in block.splitlines()]
            rows = [[cell.strip() for cell in row] for row in rows]
            parts.append(r"\begin{center}" + "\n" +
                         r"\begin{tabularx}{\linewidth}{@{}p{0.10\linewidth}p{0.28\linewidth}X@{}}" + "\n" + r"\toprule")
            for index, row in enumerate(rows):
                if index == 1 and all(re.fullmatch(r":?-+:?", cell) for cell in row):
                    continue
                if len(row) != 3:
                    raise ValueError("Proposal tables must have exactly three columns")
                parts.append(" & ".join(tex_text(cell) for cell in row) + r" \\")
                if index == 0:
                    parts.append(r"\midrule")
                elif index < len(rows) - 1:
                    parts.append(r"\addlinespace[3pt]")
            parts.extend([r"\bottomrule", r"\end{tabularx}", r"\end{center}"])
            continue
        list_lines = block.strip().splitlines()
        if list_lines and all(re.match(r"^(?:- |\d+\. )", line) for line in list_lines):
            environment = "itemize" if list_lines[0].startswith("- ") else "enumerate"
            parts.append(r"\begin{" + environment + "}")
            parts.extend(r"\item " + tex_text(re.sub(r"^(?:- |\d+\. )", "", line)) for line in list_lines)
            parts.append(r"\end{" + environment + "}")
            continue
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        if not text:
            continue
        if text.startswith("### "):
            parts.append(r"\subsection{" + tex_escape(text[4:]) + "}")
        elif text.startswith("## "):
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
    if separate_references:
        parts.append(r"\clearpage")
    parts.extend([r"\bibliographystyle{plainnat}",
                  r"\bibliography{references}", r"\end{document}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/proposal/proposal.md")
    parser.add_argument("--latex-output", type=Path, default=ROOT / "docs/proposal/proposal.tex")
    parser.add_argument("--inline-references", action="store_true",
                        help="Keep references in the normal flow for a concise, page-limited edition.")
    parser.add_argument("--natural-spacing", action="store_true",
                        help="Do not stretch vertical spacing to align page bottoms.")
    args = parser.parse_args()
    build_latex(args.source, args.latex_output, separate_references=not args.inline_references,
                natural_spacing=args.natural_spacing)
