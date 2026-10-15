# Multi Object Segmentation and Tracking

CS550 final project by **Jingdi Wu, Yupu Guo, and Christina Ross**, Rutgers University, Fall 2026.

The October 15 revision retains two pretrained baselines: YOLO11s-seg + class-gated ByteTrack (A0) and detector-assisted SAM 2.1 Hiera Tiny (B0). It adds a shared research question: when a new observation arrives, does retaining history help recovery, or does reinitializing the target work better? ByteTrack's motion state and SAM's visual history are studied through paired retain/reset experiments with fixed model weights. The study connects system comparison, error diagnosis, recovery curves, and at most one evidence-supported automatic policy.

## Proposal

- [English model study guide](docs/model-guide/README.md): model roles, pipeline examples, evaluation metrics, and proposal-review questions.
- [Concise English proposal PDF](docs/proposal/proposal_short.pdf)
- [Concise Chinese review PDF](docs/proposal/proposal_short_zh.pdf)
- [Concise English source](docs/proposal/proposal_short.md) / [Chinese source](docs/proposal/proposal_short_zh.md)
- [Full English review PDF](docs/proposal/proposal.pdf)
- [Full Chinese review PDF](docs/proposal/proposal_zh.pdf)
- [Chinese Markdown](docs/proposal/proposal_zh.md)
- [LaTeX source](docs/proposal/proposal.tex)
- [Markdown content](docs/proposal/proposal.md)
- [BibTeX references](docs/proposal/references.bib)

The proposal and its LaTeX support files remain together in [docs/proposal](docs/proposal). It now uses the supplied NeurIPS 2026 template with its standard single-column layout. The supplied archive is fully unpacked in [templates/neurips](templates/neurips). The earlier ACL files remain available in [templates/acl](templates/acl) and as inactive support files in the proposal folder.

Both editions include an abstract, related work, experimental design, evaluation, and all three authors' names. Student ID lines are omitted at the team's request. The complete team-reviewed design is retained in the full edition: five English body pages plus one reference page, and four Chinese body pages plus one reference page. At the team's request, the concise edition allows up to three body pages, with references on a separate page. Content flows naturally without manual chapter breaks or stretched paragraph spacing, preserving headings, readable paragraphs and a four-group comparison table. The current English edition has three body pages; the Chinese edition has two. The original course-format source is recorded in [template provenance](docs/proposal/TEMPLATE-PROVENANCE.md); the current review format does not reinterpret that source. Coursework submission is performed by the human, never by an agent.

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

For the concise edition, generate the separate source with references on their own page:

```bash
python tools/build_proposal.py --source docs/proposal/proposal_short.md --latex-output docs/proposal/proposal_short.tex --natural-spacing
python tools/build_proposal_zh.py --source docs/proposal/proposal_short_zh.md --output docs/proposal/proposal_short_zh.pdf
```

Compile `proposal_short.tex` with the same unchanged style and `references.bib`, using the isolated-build procedure above. The concise and full PDFs are separate files; do not overwrite the complete review edition when shortening the course proposal.

The Chinese version follows the English version section by section and is intended for team review, not as a separate conference-template submission. Rebuild it with `python tools/build_proposal_zh.py` (requires ReportLab and Microsoft YaHei fonts; use `--font-regular` and `--font-bold` for other compatible CJK TrueType fonts).

## Revised experiment scope

The target subset remains 200 labeled YouTube-VIS 2021 videos, with seed 550 and whole-video 60/20/20 splits: 120 for development, 40 for validation, and 40 held out for evaluation. The categories remain person, dog, cat, horse, and car. Split videos before sampling frames. Counts and coverage are planned until verified.

| Controlled branch | Treatment at the correction event |
| --- | --- |
| A-H | Keep ByteTrack's motion state and apply a normal Kalman update |
| A-R | Initialize motion state from the same box, with zero velocity and the default initial covariance |
| B-H | Keep SAM's target history and add the same box prompt |
| B-R | Clear the target's old inference state and initialize it from that box |

H/R branches within a pipeline share the pre-correction run, target ID, correction information, and normal subsequent input schedule. A reset does not assign a new external ID or reset other targets. The two systems' internal state types are different; compare each H/R pair first, then analyze the conditions and duration of the differences.

Actual YOLO boxes and annotation-derived current-frame reference boxes are separate diagnostic conditions. The controlled experiment explicitly supplies the target correspondence; full automatic A0/B0 results do not use that correspondence or annotation prompts. Already-deleted tracks are reported separately from common events where both systems retain usable state. Recovery experiments measure correct target following, recovery time and recurrence, with association diagnostics for ByteTrack and mask diagnostics for SAM.

Fix event selection, thresholds, observation windows, and any follow-up policy on development/validation data before held-out evaluation. Model weights stay fixed throughout the core study. A simple automatic policy is optional only if the controlled findings support it; the paired analysis remains a complete research result if no policy improves the systems.

Short local inference has been verified on the RTX 3080 (10 GB), but the complete automatic SAM wrapper, paired state interventions, and benchmark evaluation still require implementation and pilots. School runs must observe current Rutgers access and scheduling rules; GPU availability is not assumed.

## Pilot resources

The personal teaching website and lesson code (`learning/`), generated results (`outputs/`), video files, datasets, model weights, and private connection notes remain local and are excluded from Git. Shared model explanations are available in the [English study guide](docs/model-guide/README.md). Local demonstrations are smoke tests, not the proposal's complete automatic pipeline or benchmark results.

Download the pretrained checkpoints and small smoke-test videos used by the proposed pipelines:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1
```

The downloaded files are ignored by Git. Their source URLs, sizes, and SHA-256 hashes are recorded in `resources/downloaded-resources.json`. See [data/README.md](data/README.md) for the authenticated YouTube-VIS 2021 download and video-level subset procedure, and [models/README.md](models/README.md) for model roles and upstream sources.
