# ACML 2026 template provenance

This directory preserves the unmodified class distributed with the **Asian Conference on Machine Learning (ACML) 2026 conference-track template**. ACML is distinct from ACM and its `acmart` class. The proposal uses the ACML layout as a course-document adaptation; it is not an accepted ACML paper or a PMLR publication.

## Upstream sources

- Official conference instructions: <https://www.acml-conf.org/2026/calls/papers/>
- Official archive: <https://www.acml-conf.org/2026/downloads/ACML_camera_ready.zip>
- PMLR formatting and preparation-system information: <https://proceedings.mlr.press/faq.html>
- JMLR package source distribution: <https://mirrors.ctan.org/macros/latex/contrib/jmlr.zip>
- License text: <https://www.latex-project.org/lppl/lppl-1-3c.txt>

Retrieved and inspected on October 7, 2026. The archive's `ACML_camera_ready/jmlr.cls` identifies itself as **2022/02/09 v1.30**, maintained by Nicola Talbot. It is copied byte for byte to this directory. The upstream sample source, sample PDF, illustration, bibliography, and macOS metadata are not vendored here. The sample source/PDF and archive were inspected in a temporary directory.

## SHA-256 checksums

| Artifact | SHA-256 |
| --- | --- |
| Downloaded `ACML_camera_ready.zip` | `4e0752d3d5da2ee99a1256aa5f91fba841635a6f341befd1923fa3ff45f91bcb` |
| Vendored `jmlr.cls` | `56d600a80832cf919d379295e15ff5a7b754ddbb61c54a12678b33d47e5ac1fd` |
| Upstream `acml26_submission_template.tex` | `3e4f80ff1629b24181c9f2a1a4fc8159d4b75374896a7f270258d3b969a76d2e` |
| Upstream `acml26_submission_template.pdf` | `d078bf3ea057cd52b041fc0d7197f95bcf04ab41ae1559e096616aa6e2e5dc0f` |
| Vendored `LICENSE-LPPL-1.3c.txt` | `3d262cdf34dafa6955f703c634a8c238ec44109bc8dd6ef34fb7aa54809f7e66` |

## License and dependencies

The `jmlr.cls` header states copyright **2022 Nicola Talbot**, with distribution/modification under the **LaTeX Project Public License version 1.3 or later**. The complete, unmodified LPPL 1.3c text is included as `LICENSE-LPPL-1.3c.txt`. The class retains its original license and maintainer notices. The current source distribution is linked above; no support from ACML, PMLR, or the class maintainer is implied for this course adaptation.

The ACML archive contains no additional `.sty` or `.bst` files. Its class requires standard TeX packages including `jmlrutils`, `natbib`, `algorithm2e`, and `hyperref`, and selects `plainnat.bst`. These dependencies should be supplied by the TeX distribution/compiler rather than copied into this directory. PMLR supports LaTeX preparation; any Word companion is an editable approximation of the layout, not an official Word template.

## Verified formatting

The actual ACML sample begins with `\documentclass[wcp]{jmlr}`. Preserve this option set instead of introducing `twocolumn` or a different point size.

- Single-column body with **11 pt** article defaults and Computer Modern roman typography.
- US Letter paper, with **6.0 in text width** and **8.5 in text height**. The class sets both side-margin registers to `0.25in`, giving 1.25 in physical left/right margins under normal TeX positioning. It sets `\topmargin` to `-0.5in` and adds `0.25in` to `\headsep`; retain the class's header/body positioning instead of imposing a separate geometry package.
- Centered bold title, author/affiliation block, abstract, keyword list, and numbered sections.
- `natbib` author-year citations with `plainnat` bibliography style, rather than numbered bracket citations.
- The sample suppresses page numbers with `\pagenumbering{gobble}` and clears the page-range metadata before `\maketitle`.

## Publication metadata and course adaptation

The official sample sets `\jmlryear{2026}`, `\jmlrworkshop{ACML 2026}`, and `\editors{Andy Song, Bo Han and Sarah Erfani}`. It leaves `\jmlrvolume` commented out. The class normally prints a PMLR header and an automatic copyright line containing the year and abbreviated author names.

For a named course proposal, preserve the supplied author names and Rutgers affiliation; do not invent author emails or a proceedings volume. The conference's anonymization requirement applies to actual conference submissions, not this named course assignment. Clearly identify the document as a CS550 proposal. Metadata changes belong in the proposal source and must leave `jmlr.cls` unmodified. Supported overrides include:

```tex
\jmlrproceedings{}{CS550 Project Proposal}
\jmlryear{2026}
\jmlrworkshop{ACML 2026 style}
\jmlrvolume{}
\jmlrpages{}
\editors{}
\pagenumbering{gobble}
```

If the course version omits the template's first-page copyright footer, override it explicitly in the proposal source:

```tex
\makeatletter
\renewcommand*{\@titlefoot}{}
\makeatother
```

This removes that document footer; it does not remove or change the license notices in the upstream class file. Course-specific header/footer metadata is an intentional adaptation of the official template, not a change to its fonts or page geometry. The actual conference page limit should not replace the course's two-page proposal requirement.
