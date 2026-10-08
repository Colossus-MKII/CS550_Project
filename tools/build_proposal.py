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
\hypersetup{hidelinks}
\setcitestyle{authoryear,round}
% Named course proposal.
\title{TITLE}
\author{NAMES}
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
    parts.extend([r"\clearpage", r"\bibliographystyle{plainnat}",
                  r"\bibliography{references}", r"\end{document}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/proposal/proposal.md")
    parser.add_argument("--latex-output", type=Path, default=ROOT / "docs/proposal/proposal.tex")
    args = parser.parse_args()
    build_latex(args.source, args.latex_output)
