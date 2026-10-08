# Multi Object Segmentation and Tracking

CS550 final project by **Jingdi Wu, Yupu Guo, and Christina Ross**, Rutgers University, Fall 2026.

The project compares YOLO segmentation with ByteTrack/BoT-SORT, SAM 2.1, SAM-Track (SAM + DeAOT), and OpenCV MOG2/KNN across different object categories. We will study segmentation accuracy, identity stability, robustness, and processing cost using MOTS-style metrics. YOLO fine-tuning is the main adaptation experiment; SAM 2.1 and DeAOT fine-tuning depend on the available GPU budget. OpenCV adaptation consists of parameter tuning and online background updates.

## Proposal

- [Final PDF](docs/proposal/proposal.pdf)
- [LaTeX source](docs/proposal/proposal.tex)
- [Markdown content](docs/proposal/proposal.md)
- [BibTeX references](docs/proposal/references.bib)

The proposal and its LaTeX support files are together in [docs/proposal](docs/proposal). It uses the supplied ACL template with a standard two-column layout. The original ACL ZIP is fully unpacked in [templates/acl](templates/acl), including its nested `latex` directory, README, and formatting examples. The course requires a two-page proposal and an eight-page final report excluding references.

## Build

The Python builder uses the standard library and generates `docs/proposal/proposal.tex` from the Markdown content:

```bash
python tools/build_proposal.py
```

Upload the plain LaTeX, bibliography, and support files from `docs/proposal` to Overleaf and select `proposal.tex` as the main document. To compile locally with Tectonic:

```bash
proposal_build_dir=$(mktemp -d)
cp docs/proposal/proposal.tex docs/proposal/references.bib docs/proposal/*.sty docs/proposal/*.bst "$proposal_build_dir/"
tectonic --untrusted --keep-logs --outdir "$proposal_build_dir" "$proposal_build_dir/proposal.tex"
cp "$proposal_build_dir/proposal.pdf" docs/proposal/proposal.pdf
rm -r "$proposal_build_dir"
```

Inspect the resulting PDF after edits to confirm the layout and page count.
