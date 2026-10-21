"""Render the repository's proposal as a local, auditable reading snapshot.

Only explicitly named proposal/template files are copied. This small Markdown
renderer supports the headings, paragraphs, tables, links and emphasis used by
our proposal; raw HTML is escaped and links must use HTTP(S).
"""

from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROPOSAL_ROOT = Path(__file__).resolve().parents[1] / "docs" / "proposal"
FILES = {"zh": ("proposal_zh.md", "proposal_zh.pdf"),
         "en": ("proposal.md", "proposal.pdf")}
SHORT_FILES = {"zh": ("proposal_short_zh.md", "proposal_short_zh.pdf"),
               "en": ("proposal_short.md", "proposal_short.pdf")}
TEMPLATE_ROOT = PROPOSAL_ROOT.parents[1] / "templates" / "neurips"
LATEX_FILES = ("proposal.tex", "references.bib", "neurips_2026.sty")
SHORT_LATEX_FILES = ("proposal_short.tex", "references.bib", "neurips_2026.sty")
TEMPLATE_FILES = ("neurips_2026.tex", "neurips_2026.sty", "checklist.tex")


def latex_downloads():
    """Build source-only archives; never sweep a directory or include credentials."""
    groups = (
        ("proposal-latex.zip", PROPOSAL_ROOT, LATEX_FILES, "proposal.tex", "current-proposal"),
        ("proposal-short-latex.zip", PROPOSAL_ROOT, SHORT_LATEX_FILES,
         "proposal_short.tex", "concise-proposal"),
        ("neurips-2026-template-files.zip", TEMPLATE_ROOT, TEMPLATE_FILES,
         "neurips_2026.tex", "retained-template-files-repacked"),
    )
    downloads = {}
    for filename, root, names, main, kind in groups:
        sources = {name: (root / name).read_bytes() for name in names}
        members = {name: {"bytes": len(data), "sha256": sha256(data).hexdigest()}
                   for name, data in sources.items()}
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in sources.items():
                # Stable metadata makes unchanged input produce identical archives.
                info = ZipInfo(name, date_time=(2026, 10, 13, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
        downloads[filename] = {
            "data": buffer.getvalue(), "kind": kind, "main_file": main, "members": members,
        }
        if kind in ("current-proposal", "concise-proposal"):
            downloads[main] = {
                "data": sources[main], "kind": kind + "-main-source",
                "required_support_files": ["references.bib", "neurips_2026.sty"],
            }
    return downloads


def inline(text):
    tokens = re.compile(r"\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^\s)]+)\)")
    result, start = [], 0
    for match in tokens.finditer(text):
        result.append(escape(text[start:match.start()]))
        strong, code, label, url = match.groups()
        if strong is not None:
            result.append(f"<strong>{escape(strong)}</strong>")
        elif code is not None:
            result.append(f"<code>{escape(code)}</code>")
        else:
            result.append(f'<a href="{escape(url, quote=True)}" target="_blank" '
                          f'rel="noopener noreferrer">{escape(label)}</a>')
        start = match.end()
    result.append(escape(text[start:]))
    return "".join(result)


def render_markdown(markdown):
    lines = markdown.splitlines()
    result, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        heading = re.match(r"^(#{1,6}) (.+)$", line)
        if heading:
            level = min(6, len(heading[1]) + 2)
            result.append(f"<h{level}>{inline(heading[2])}</h{level}>")
            index += 1
        elif (line.startswith("|") and index + 1 < len(lines)
              and re.fullmatch(r"\|[ :|\-]+\|", lines[index + 1])):
            cells = lambda row: [inline(cell.strip()) for cell in row.strip().strip("|").split("|")]
            result.append('<div class="table-wrap"><table><thead><tr>' +
                          "".join(f'<th scope="col">{cell}</th>' for cell in cells(line)) +
                          "</tr></thead><tbody>")
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                result.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells(lines[index])) + "</tr>")
                index += 1
            result.append("</tbody></table></div>")
        elif re.match(r"^(?:- |\d+\. )", line):
            ordered = not line.startswith("- ")
            tag = "ol" if ordered else "ul"
            pattern = r"^\d+\. (.+)$" if ordered else r"^- (.+)$"
            result.append(f"<{tag}>")
            while index < len(lines):
                item = re.match(pattern, lines[index])
                if not item:
                    break
                result.append("<li>" + inline(item[1]) + "</li>")
                index += 1
            result.append(f"</{tag}>")
        else:
            paragraph = []
            while index < len(lines) and lines[index].strip():
                if paragraph and re.match(r"^(#|\|)", lines[index]):
                    break
                item = lines[index]
                paragraph.append(inline(item.rstrip()) + ("<br>" if item.endswith("  ") else ""))
                index += 1
            result.append("<p>" + "\n".join(paragraph) + "</p>")
    return "\n".join(result)


def prepare_proposals(output):
    # Read every source before updating any snapshot, so missing inputs fail clearly.
    sources = {name: (PROPOSAL_ROOT / name).read_bytes()
               for edition in (FILES, SHORT_FILES) for pair in edition.values() for name in pair}
    downloads = latex_downloads()
    destination = Path(output) / "proposal"
    destination.mkdir(exist_ok=True)
    manifest = {"source_directory": "docs/proposal", "files": {}, "downloads": {}}
    for name, item in downloads.items():
        content = item["data"]
        (destination / name).write_bytes(content)
        manifest["downloads"][name] = {
            **{key: value for key, value in item.items() if key != "data"},
            "bytes": len(content), "sha256": sha256(content).hexdigest(),
        }
    for name, content in sources.items():
        snapshot = name + ".txt" if name.endswith(".md") else name
        (destination / snapshot).write_bytes(content)
        manifest["files"][name] = {"snapshot": snapshot, "bytes": len(content),
                                   "sha256": sha256(content).hexdigest()}
    pages = {}
    for language, (markdown_name, pdf_name) in FILES.items():
        short_markdown, short_pdf = SHORT_FILES[language]
        pages[language] = {
            "html": render_markdown(sources[markdown_name].decode("utf-8-sig")),
            "pdf": f"proposal/{pdf_name}", "source": f"proposal/{markdown_name}.txt",
            "source_name": f"docs/proposal/{markdown_name}",
            "hash": manifest["files"][markdown_name]["sha256"],
            "latex_bytes": len(downloads["proposal-latex.zip"]["data"]),
            "template_bytes": len(downloads["neurips-2026-template-files.zip"]["data"]),
            "tex_bytes": len(downloads["proposal.tex"]["data"]),
            "short_pdf": f"proposal/{short_pdf}",
            "short_source": f"proposal/{short_markdown}.txt",
            "short_pdf_bytes": len(sources[short_pdf]),
            "short_latex_bytes": len(downloads["proposal-short-latex.zip"]["data"]),
            "short_tex_bytes": len(downloads["proposal_short.tex"]["data"]),
        }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return pages
