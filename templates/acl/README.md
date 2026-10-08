# User-provided ACL template provenance

This directory uses the exact local archive supplied by the user: `Association_for_Computational_Linguistics__ACL__conference.zip` at the repository root. It is an **Association for Computational Linguistics (*ACL)** template. It replaces the earlier ACML template choice for the current proposal.

The archive was inspected on October 7, 2026. Files were selected by their exact archive entry names, without executing the sample documents or extracting unrelated files. `acl.sty` and `acl_natbib.bst` are copied byte for byte, with their original headers intact. The archive's sample `.tex`, bibliography examples, formatting instructions, and README were read as reference material; they are not required build support files and are not duplicated here.

## Checksums

| Source or retained file | SHA-256 |
| --- | --- |
| Local source ZIP | `3975e9198239f8a15f52e2a29d54fd989a937a7239dad5a333ea20fa073fb8fd` |
| `latex/acl.sty` → `acl.sty` | `19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de` |
| `latex/acl_natbib.bst` → `acl_natbib.bst` | `e332fd51dcea48e2a8a89754892c3cb99674a1cd70b527b661e9aaffc235e83c` |
| Archive `README.md` | `72ed13896af73eaa34bc986d54917c35ee0b60c3068461f3ad80c68cd128db0f` |
| Archive `latex/acl_latex.tex` | `75d39b038d39dd4ceda45f41092bda048afdd0eb750f5717f78be1756ce491be` |
| Archive `latex/acl_lualatex.tex` | `0d9987ba833331a996f9abcd1a03eebba7d7ae331145793e7ddb6b5ae8db27b3` |
| Archive `formatting.md` | `9e004a136c5dd43300d97e5bef5eb3a77d0e2a2d3502f0f2436ec011d1c49e9c` |
| `LICENSE-LPPL-1.3c.txt` | `3d262cdf34dafa6955f703c634a8c238ec44109bc8dd6ef34fb7aa54809f7e66` |

The embedded upstream README identifies <https://github.com/acl-org/acl-style-files/> and <https://www.overleaf.com/latex/templates/association-for-computational-linguistics-acl-conference/jvxskxpnznfj> as upstream sources. These links are provenance, not a replacement for the user's selected ZIP version.

## License notices

The archive contains no standalone license file. The `acl_natbib.bst` header expressly permits redistribution/modification under the LaTeX Project Public License, version 1 or later, and preserves Patrick W. Daly's 1994–2011 copyright and Norman Gray's 2002–2023 urlbst modification notice. A complete, unmodified LPPL 1.3c text from <https://www.latex-project.org/lppl/lppl-1-3c.txt> is included as license support for that bibliography file.

No explicit license grant for `acl.sty` was found in the provided archive; its upstream attribution and instructions remain intact. This provenance document does not assign a new license to that style file. The supplied README directs authors not to modify the style files, and the vendored files are unmodified.

## Build settings and layout

The source sample's preamble is:

```tex
\documentclass[11pt]{article}
\usepackage[review]{acl}
\usepackage{times}
\usepackage{latexsym}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
```

For this named course proposal, use `\usepackage[final]{acl}` instead of the sample's anonymous review mode. The article class remains `11pt`; the ACL package itself enables two columns. Standard compiler-supplied packages provide the external dependencies. No separate ACL document class is required.

The actual provided `acl.sty` uses A4 paper and `geometry` with `margin=2.5cm,heightrounded=true`, plus a 0.6 cm column gap. The nominal text width is 16 cm, yielding two 7.7 cm columns. Nominal body height is 24.7 cm; `heightrounded` adjusts the usable height to complete text lines. Preserve these settings rather than applying a different geometry or custom line stretch.

Times Roman is selected by the sample's `times` package. The body is 11 pt, single-spaced. The abstract is 10 pt with 12 pt baseline spacing and is inset 0.6 cm on both sides within the first column. The title and author block span both columns. The package sets the title box to `11\baselineskip`; the instructions prohibit reducing the title box below 5 cm. Names and affiliations should remain the supplied names and Rutgers University affiliation; do not invent email addresses.

The archive's formatting instructions describe a 15 pt title, but its actual `acl.sty` uses the `\Large` macro based on `\xivpt` (14.4 pt in the current LaTeX format) with a 16 pt baseline. Preserve the actual supplied style rather than replacing its title font to reconcile this difference. Author names and section headings use `\large`, implemented as 12 pt with a 14 pt baseline. Captions are 10 pt with a 12 pt baseline. Footnotes use 9 pt with a 10 pt baseline.

A temporary compilation probe using the retained style, the sample's article/Times/T1 preamble, and Tectonic 0.17.0 confirmed the effective values: body 10.95 pt / 13.6 pt baseline (LaTeX's nominal 11 pt), title 14.4 pt / 16 pt, authors 12 pt / 14 pt, abstract 10 pt / 12 pt, and footnotes 9 pt / 10 pt. The effective text area was 455.24411 × 704.60031 TeX pt; each column was 219.08614 pt wide with a 17.07182 pt gap. The title box was 149.60007 pt (about 5.26 cm), and paragraph indentation was 10.95 pt. The probe did not modify the retained template files.

The references use `natbib` author-year citations and the included `acl_natbib.bst`. Bibliography entries are alphabetized, and the section heading is unnumbered “References.” Use `\citet` for narrative citations and `\citep` for parenthetical citations. The source describes the bibliography format as approximately APA. The course's proposal length requirement remains controlling; generic conference submission page limits in the archive do not replace it.

## Named and anonymous modes

| ACL package option | Names | Line numbers | Page numbers |
| --- | --- | --- | --- |
| `final` (also the default) | Supplied names/affiliations | No | No |
| `preprint` | Supplied names/affiliations | No | Yes |
| `review` | “Anonymous ACL submission” | Yes | Yes |

The course proposal uses **final** formatting to show Jingdi Wu, Yupu Guo, and Christina Ross. This selects a named layout; it does not claim the proposal was accepted by ACL. The provided package has no PMLR-style proceedings volume, editor block, or automatic author copyright footer.
