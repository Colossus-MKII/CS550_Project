# Multi Object Segmentation and Tracking

CS550 final project by **Jingdi Wu, Yupu Guo, and Christina Ross**, Rutgers University, Fall 2026.

The October 13 revision compares two pretrained baselines: YOLO11s-seg + class-gated ByteTrack (A0) and detector-assisted frozen SAM 2.1 Hiera Tiny (B0). A prioritized, budgeted YOLO fine-tuning study then reuses one adapted checkpoint in both pipelines (A1/B1). We test whether detector improvements translate into segmentation and identity gains, using mask HOTA/DetA/AssA, IDF1, detector diagnostics, runtime, and memory. Fine-tuning is feasibility-gated; the pretrained study remains the minimum deliverable. SAM/DeAOT training and additional pipelines are outside this revision.

## Proposal

- [English model study guide](docs/model-guide/README.md): model roles, pipeline examples, evaluation metrics, and proposal-review questions.
- [Revised English PDF](docs/proposal/proposal.pdf)
- [Chinese review PDF](docs/proposal/proposal_zh.pdf)
- [Chinese Markdown](docs/proposal/proposal_zh.md)
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

The Chinese version follows the English version section by section and is intended for team review, not as a separate conference-template submission. Rebuild it with `python tools/build_proposal_zh.py` (requires ReportLab and Microsoft YaHei fonts; use `--font-regular` and `--font-bold` for other compatible CJK TrueType fonts).

## Revised experiment scope

The target subset remains 200 labeled YouTube-VIS 2021 videos, with seed 550 and whole-video 60/20/20 splits: 120 for the planned adaptation study, 40 for validation, and 40 held out for evaluation. Split videos before sampling training frames. Both adapted pipelines reuse the same YOLO checkpoint selected on validation data, while thresholds and downstream policies remain fixed within each before/after pair. Counts and category coverage must be verified and frozen before tuning; these are planned counts, not a claim that the labeled dataset is already downloaded. Teaching clips are excluded from scoring and training.

Short local inference has been verified on the RTX 3080 (10 GB), but the complete automatic SAM wrapper and YOLO training still require pilots. School runs must observe current Rutgers access and scheduling rules; GPU availability is not assumed.

## Pilot resources

The personal teaching website and lesson code (`learning/`), generated results (`outputs/`), video files, datasets, model weights, and private connection notes remain local and are excluded from Git. Shared model explanations are available in the [English study guide](docs/model-guide/README.md). Local demonstrations are smoke tests, not the proposal's complete automatic pipeline or benchmark results.

Download the pretrained checkpoints and small smoke-test videos used by the proposed pipelines:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1
```

The downloaded files are ignored by Git. Their source URLs, sizes, and SHA-256 hashes are recorded in `resources/downloaded-resources.json`. See [data/README.md](data/README.md) for the authenticated YouTube-VIS 2021 download and video-level subset procedure, and [models/README.md](models/README.md) for model roles and upstream sources.
