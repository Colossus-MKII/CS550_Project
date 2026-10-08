# Multi Object Segmentation and Tracking

CS550 final project by **Jingdi Wu, Yupu Guo, and Christina Ross**, Rutgers University, Fall 2026.

The project compares YOLO segmentation with ByteTrack/BoT-SORT, SAM 2.1, SAM-Track (SAM + DeAOT), and OpenCV MOG2/KNN across different object categories. We will study segmentation accuracy, identity stability, robustness, and processing cost using MOTS-style metrics. YOLO fine-tuning is the main adaptation experiment; SAM 2.1 and DeAOT fine-tuning depend on the available GPU budget. OpenCV adaptation consists of parameter tuning and online background updates.

## Proposal

- [Final PDF](docs/proposal/proposal.pdf)
- [LaTeX source](docs/proposal/proposal.tex)
- [Markdown content](docs/proposal/proposal.md)
- [BibTeX references](docs/proposal/references.bib)

The proposal and its LaTeX support files remain together in [docs/proposal](docs/proposal). It now uses the supplied NeurIPS 2026 template with its standard single-column layout. The supplied archive is fully unpacked in [templates/neurips](templates/neurips). The earlier ACL files remain available in [templates/acl](templates/acl) and as inactive support files in the proposal folder.

The proposal has two content pages excluding references and includes an abstract, related work, a proposed method, and all three authors' names. References begin on a separate page. Student ID lines are omitted at the team's request. Each student submits the same PDF individually. The final report limit is eight pages excluding references.

## Build

The Python builder uses the standard library and generates `docs/proposal/proposal.tex` from the Markdown content:

```bash
python tools/build_proposal.py
```

Upload `proposal.tex`, `references.bib`, and `neurips_2026.sty` from `docs/proposal` to Overleaf and select `proposal.tex` as the main document. To compile locally with Tectonic:

```bash
proposal_build_dir=$(mktemp -d)
cp docs/proposal/proposal.tex docs/proposal/references.bib docs/proposal/neurips_2026.sty "$proposal_build_dir/"
tectonic --untrusted --keep-logs --outdir "$proposal_build_dir" "$proposal_build_dir/proposal.tex"
cp "$proposal_build_dir/proposal.pdf" docs/proposal/proposal.pdf
rm -r "$proposal_build_dir"
```

Inspect the resulting PDF after edits to confirm the layout and page count.
