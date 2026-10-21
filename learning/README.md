# CS550 experiment workbench and learning references

## Clone and preview the website source

本目录现在纳入 Git：网站生成器、教学示例源码、HTML/CSS/JS、图标、预览服务器和测试。此前网站开发仅在本地进行，本次是首个网站源码快照；不会补造先前的提交历史。完整实验输出、数据、权重、视频、生成网页、浏览器截图和原始机器运维日志继续保留在本地。

From a repository checkout, use Python 3.10–3.12 and an activated virtual environment:

```bash
python -m pip install -r learning/requirements-web.txt
python -m learning.preview --output outputs/learning/source-preview
python -m learning.serve --run source-preview --port 8765
```

Open `http://127.0.0.1:8765/cs550-tracking-lab/`. This source-only preview builds all bilingual page families without PyTorch, model weights or inference. It does not include saved scientific measurements or videos; pages with no local evidence show their unavailable state. Choose a new output directory for another preview: existing directories and measured runs are deliberately refused. The preview binds to loopback by default. Use another port if 8765 is already in use.

To run the portable website tests:

```bash
python -m pip install pytest==8.4.2
python -m pytest learning/tests -q
```

One saved-cohort integration check requires separately retained local results and is skipped when those assets are absent. Set `CS550_SITE_OUTPUT` to the existing site-output directory to run that optional check. Template, source-only generation, navigation structure, import-validation and HTTP-preview tests run without those assets. Optional browser checks are in `tests/check_*.cjs`; `tests/reading_position_cua.mjs` can also use an existing connected browser tab with a caller-supplied artifact directory and base URL.

See [VALIDATION_SUMMARY.md](VALIDATION_SUMMARY.md) for the shared verification record. The sections below document the full local workflow, including optional model-backed lessons and importing saved experiments; those steps require resources excluded from Git.

Measured H/R follow-up: `recovery.html` / `recovery.en.html` now connect the corrected A0/B0 baseline to the completed 16-branch rider/cat study. The reader follows baseline selection → same-box retain/reset → paired scores/curves → four-group videos → evidence and limits. Actual YOLO and annotation-reference boxes are separate collapsible conditions; baseline links open the exact video/frame. The homepage, baseline results, protocol, program map and run history link into this evidence. Early 24-branch execution smoke tests remain distinct from this measured batch, and unrun candidates are not marked complete.

Import an existing completed batch with `python -m learning.recovery_page --source experiments/runs/recovery-rider-cat-20261017-3080 --output outputs/learning/20261011-095748-9d89fd`, then refresh the existing report. The importer requires verification, full-inference repeat proof tied to the source summary, exact corrected-baseline identity, complete branch coverage and source fingerprints. It exposes only reviewed media, score curves, provenance and code; raw masks and absolute-path summaries are excluded. CSV downloads use byte-identical `.csv.txt` aliases with `.csv` download filenames, preserving the existing server's extension allowlist and running process.

Baseline correction (2026-10-17): the site now selects `stage1-20261017-sync-verified`, after a complete five-video rerun with the SAM CPU-read synchronization guard and an independent pixel-exact full inference repeat. Scores, all five comparison videos/curves, representative cases and bilingual attribution notes were regenerated. Legacy evidence remains intact; the original active manifest is retained as `pilot-results/manifest-before-sync.json`. Legacy rider-25/horse-35 anomalies are withdrawn as memory-failure evidence. The program map now distinguishes lifecycle retirement, duplicate tracks and genuinely poor rider segmentation, and shows a read-only eligibility audit for the next, not-yet-run event set. The previous 24 H/R branches are development execution checks, not a formal benchmark.

The default `index.html` / `index.en.html` introduces the research question and defines A0/B0 before showing scores. A four-question route connects model concepts to their actual program steps, evaluation evidence and recovery study; learning and experimentation are not separate silos. The homepage retains direct handbook and results actions. The remaining content prioritizes current phase, verified run, scores and representative failures, pending recovery preparation, data and documents. `runs.html` / `runs.en.html` records process, configuration and evidence; `documents.html` / `documents.en.html` centralizes proposal editions and sources. These are read-only records, not a live job monitor or a launcher.

The seven-lesson course is preserved at `handbook.html` / `handbook.en.html`, including its original videos, progress, frame controls and metric examples. Its primary action starts YOLO, not a program page. The local course sequence is model roles → metrics → research design; optional background remains separate. Six chapter-end connections explain how the concept is used in this project and link to the precise program step, data viewer, score report or recovery protocol. Experiment pages offer relevant prerequisite links back to lessons. Project/Learn links stay visible in the header. The handbook outline uses four native collapsible groups; the current chapter's group opens automatically and its link stays visible inside the sidebar. Readers can switch groups manually or use Current section to return to their place. Learning pages share a blue accent across navigation, links, buttons and controls; project pages retain the default green. Project destinations are grouped into Project & progress, Results & research, and Implementation & resources, with the current page group open by default. Experiment pages also have grouped local outlines, automatic current-section expansion and sidebar positioning, a page-overview link and the same Current section action. Language switching retains the actual paragraph/table row/media position and relative progress, along with expanded content and existing viewer query state; the outline follows the reading line rather than the largest visible section. No completion prerequisite is imposed. Legacy `index.html#chapter-*` bookmarks route to matching handbook sections, with fallback bookmark links when JavaScript is disabled. No H/R intervention, recovery curve or formal split is claimed complete merely because its plan is visible.

All 12 bilingual page families have an outline entry for every main section, including the reference-page overview. Current-section groups expand in the same update as the highlight; media loading, disclosure changes and program-panel changes also refresh the outline. Reading-position anchors exclude hidden panels and content inside closed disclosures. `tests/reading_position_cua.mjs` provides repeatable position, outline and mobile-menu checks through an existing connected browser tab, without launching another browser; measurements are saved under a server-excluded browser-QA directory.

This is a **local-only teaching workflow**, not the project's final evaluation code. It does not SSH to Rutgers, allocate remote GPUs, train a model, or download gated datasets. The existing five pilot videos are enough to start.

## 先看这里 / Start here

四课用同一段连续视频，依次回答：

| Lesson | What you see | What produces it |
| --- | --- | --- |
| 1. Boxes | 目标在哪里、是什么类别？ | YOLO11s-seg detection output, with masks hidden |
| 2. Masks | 哪些像素属于目标？ | The **same** YOLO prediction, with masks shown |
| 3. IDs | 这一帧与上一帧是不是同一目标？ | YOLO masks + ByteTrack box association |
| 4. Propagation | 给定目标后，能否持续描出它？ | SAM 2.1 Hiera Tiny with first-frame box prompts |

先看生成的 `handbook.html`，播放四格对比，暂停/逐帧检查，然后阅读各课代码。YOLO 不是“只识别运动”的算法：静止物体也可以被检测。ByteTrack 不生成掩码，也不需要新的分割权重。SAM 的类别标签来自初始化提示，不是它自己识别的类别。

## Expanded bilingual teaching handbook

Within the handbook, the reading sequence is **model roles and videos → research design and evaluation → mathematical implementation**. It retains the seven reading units and videos; experimental design follows the four model lessons. DeAOT remains optional background after the core material. The project homepage instead prioritizes measured results and experiment progress.

Separate bilingual pages keep the main handbook focused:

- `program.html` / `program.en.html`: the experiment-to-code map. Start with the A0/B0 data flow, use eight steps to find each file/function and its inputs/outputs, then inspect the verified pilot examples and the planned H/R recovery study. Source links open allowlisted, line-anchored references from `experiments/tracking_lab`; their SHA-256 manifest identifies them as current references, not immutable inference snapshots. Large figures/videos and startup details are opt-in. This page never imports the scientific runtime or runs models. The deeper-study preparation list is pending, not a claim that H/R is implemented.

- `experiments.html` / `experiments.en.html`: automatic A0/B0 baselines, the four A-H/A-R/B-H/B-R recovery groups, responsive protocol flow diagrams, a five-step controlled-event walkthrough, reset semantics, metric roles and scope. The stepper explains the design; it does not run inference or invent measured curves. All steps remain readable without JavaScript, and switching languages preserves the selected step.
- `math.html` / `math.en.html`: tensor shapes, box decoding, mask prototypes, optional training losses, Kalman filtering, association, SAM prompt/attention/memory operations, formal metric definitions and controlled diagnostics. Equations are native MathML generated at build time with pinned `latex2mathml`; no CDN, downloaded fonts or browser rendering library is needed.
- `research.html` / `research.en.html`: representative technical developments organized by bottlenecks, with original papers and official sources, including the difference between known methods and untested project hypotheses.

Model lessons link directly to the relevant derivations; both reference pages return to the corresponding handbook lesson. They preserve the shared theme and switch languages at the current section without changing seven-unit completion progress. Version-pinned links distinguish inspected implementation facts from proposed wrappers and experiments. External sources require internet access; the generated text and equations do not.

The generated local report now includes the complete seven-chapter course: YOLO and the `ultralytics` package; pixel masks; ByteTrack, Kalman filtering and two-stage association; SAM 2.1 prompts and memory; optional SAM-Track/DeAOT; IoU/IDF1/HOTA and computation cost; and the boundaries between the learning demo and the proposal. The discussion about appearance, retrieval of the ball, and contextual identity inference is included as a qualified FAQ, not as an annotated identity result.

The page has chapter navigation and search, code excerpts and curated source snapshots, per-video playback/frame controls, a real-frame/log inspector, and independent synthetic IoU and identity-metric experiments. Reading progress/theme are stored only in the browser. All teaching resources are local; external references are ordinary links, not runtime dependencies. There is no upload, submission, SSH, cloud API, or model-execution button.

Both `handbook.html` (Chinese) and `handbook.en.html` (English) contain the complete seven-chapter handbook, including FAQs, formulas, buttons, accessibility labels and dynamic log descriptions. Use the language link in the header. The pages share browser-local reading progress and theme; a normal language switch also carries the current chapter, frame selection, experiment settings, expanded explanations and paused video positions/speeds through session storage. Source code and numerical measurements are identical in both editions. With storage disabled, the language links still work, but transient state may not be retained. JavaScript-disabled browsers can still read either language and follow its language link.

To update an **existing** run's page without loading a model or modifying its videos/measurements:

```powershell
.venv/Scripts/python.exe -m learning.report --output outputs/learning/20261011-095748-9d89fd
```

Replace the final directory with the actual run to refresh. This command preserves previous pages as `index.before-refresh-<timestamp>.html` and, when present, `index.en.before-refresh-<timestamp>.html`. It regenerates both editions and copies only the four allowlisted learning source files into `code/*.py.txt`. These are report-generation-time snapshots, not a claim of immutable original-run provenance. Original `summary.json`, videos, prompts and JSONL measurements remain unchanged. `learning/web/tutorial.html`, `tutorial.en.html`, `tutorial.css` and `tutorial.js` are the editable report sources; keep chapter IDs, controls and template placeholders aligned between the two HTML templates. CSS, JS and prediction records are embedded in each generated page so it also works through `file://` without fetching an API.

The synthetic metric calculations deliberately cover only one ground-truth object, perfect masks on present predictions and no extra detections. They are **not a replacement for TrackEval**. The actual-video inspector reports predictions, not accuracy scores; demo videos have no ground truth.

## Run on this Windows computer

From the repository root (`CS550_Project`), after setup:

```powershell
powershell -ExecutionPolicy Bypass -File learning/start.ps1
```

Default: dog video, first 60 consecutive frames, maximum source side 640, CUDA when available, and up to two SAM objects. Every run creates a **new** folder under `outputs/learning/`; existing results are not overwritten. The HTML report opens in your browser. `-NoOpen` keeps it closed.

You may also preview in the in-app browser with `.venv/Scripts/python.exe -m learning.serve`, then open `http://127.0.0.1:8765/<run-folder>/index.html`. By default this server binds only to loopback, serves only learning outputs, supports MP4 seeking, and stops with Ctrl+C. A plain `python -m http.server` may play the video but fail to seek in some browsers because it lacks byte-range responses. No server is needed when opening `index.html` directly in a desktop browser.

### Explicit network access (opt-in)

```powershell
.venv/Scripts/python.exe -m learning.serve --host 0.0.0.0 --port 8765 --run 20261011-095748-9d89fd
```

Network binding requires one existing `--run`. The selected report is exposed at
`/cs550-tracking-lab/index.html` (Chinese) and `/cs550-tracking-lab/index.en.html`
(English). `/` redirects to the stable Chinese URL; old timestamp/run-prefixed
links redirect to the corresponding stable page or asset, preserving query strings.
The experiment folder stays unchanged on disk. Other runs, HTML backups
and browser-QA folders are blocked. It provides no authentication or HTTPS: anyone who can
reach it can download the exposed teaching videos, logs and proposal sources.
Python's development HTTP server is not a production hosting stack. No upload or
remote-command endpoint is added. Firewall/NAT rules are independent of binding.

Machine-specific launchers, connection notes and firewall configuration are not
part of the shared source. Explicit network binding does not configure a router
or firewall. Actual off-device connectivity must be tested separately; a request
from the same computer does not verify external reachability.

Only YOLO/ByteTrack:

```powershell
.venv/Scripts/python.exe -m learning.run --lesson yolo --max-frames 120 --open
```

Try another existing clip:

```powershell
.venv/Scripts/python.exe -m learning.run --video data/pilot/videos/05_default_juggle.mp4 --classes person --max-frames 120 --open
```

Manually select an unfamiliar object for SAM (drag a box, then press Enter; Esc cancels):

```powershell
.venv/Scripts/python.exe -m learning.run --lesson sam2 --video data/pilot/videos/03_blocks.mp4 --pick-box --open
```

This is useful for showing that SAM can segment a prompted object outside the detector's target categories. It is **not** an automatic benchmark configuration. Manual coordinates are also supported with `--box X1 Y1 X2 Y2`, in pixels of the **resized** first frame. Labels become `selected object`, not an invented semantic category.

Explore one variable at a time:

```powershell
# Show all 80 COCO classes instead of the proposal's five categories.
.venv/Scripts/python.exe -m learning.run --classes all --open

# Compare a stricter detector threshold against the default 0.1.
# This also changes which low-score candidates ByteTrack can recover.
.venv/Scripts/python.exe -m learning.run --conf 0.5 --open

# A later segment of the SAME video; local source frame 30 becomes lesson frame 0.
.venv/Scripts/python.exe -m learning.run --start-frame 30 --max-frames 60 --open

# CPU fallback is possible but SAM is slow; start tiny.
.venv/Scripts/python.exe -m learning.run --device cpu --max-frames 5 --open
```

## Install / reproduce

Use Python **3.10–3.12** for these pinned lessons (3.12 was used here). Pass the path of a compatible Python; your system's default Python may be newer.

```powershell
powershell -ExecutionPolicy Bypass -File learning/setup.ps1 -Python "C:\path\to\python312\python.exe"
```

It creates only a project `.venv`, installs PyTorch 2.7.1 / torchvision 0.22.1 CUDA 12.8 wheels from the official PyTorch index, installs `requirements.txt`, and installs official Meta SAM 2 at commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`. The CUDA PyTorch download alone is about 3.3 GB; allow several GB more for installation. `-CpuOnly` uses the CPU wheel index. Existing global Python packages and GPU drivers are not modified. Do not share or commit `.venv`.

Meta recommends Linux/WSL for SAM 2. This native-Windows learning setup disables the optional custom CUDA connected-components extension (`SAM2_BUILD_CUDA=0`) and its small-hole cleanup. GPU tensor inference still runs through PyTorch CUDA. This setting must be recorded in any later evaluation. No CUDA compiler or WSL installation is required for this version of the learning workflow.

```powershell
.venv/Scripts/python.exe -m learning.run --check
.venv/Scripts/python.exe -m pytest learning/tests -q
```

If models or demo videos are missing, use the existing `tools/download_project_resources.ps1`. The runner verifies checkpoint hashes against `resources/downloaded-resources.json` before loading. Do not replace trusted weight files with unknown pickle-based checkpoints. Versions and checkpoint hashes are saved per run; full dependency versions are in `environment.txt`.

## Read the code in this order

1. `yolo_lessons.py`: `detector.predict()` produces boxes and masks; `tracker.track(..., persist=True, tracker="bytetrack.yaml")` associates IDs. Two YOLO instances prevent tracker state contaminating the plain prediction lesson. This uses more memory than an optimized single-pipeline experiment.
2. `sam2_lesson.py`: `init_state()` → `add_new_points_or_box()` → `propagate_in_video()`. The caller supplies object IDs; binary masks use `logits > 0`. Video/state CPU offload and BF16 on CUDA reduce VRAM demands but still consume system RAM.
3. `run.py`: connects lessons and validates resources/arguments. It deliberately accepts only local video files.
4. `common.py` and `report.py`: video decoding, mask overlays, H.264 output and the offline HTML study page. There is no network server or cloud inference requirement.

## What is saved?

The bilingual handbook includes the full current proposal at `#proposal`, rendered
directly from `docs/proposal/proposal.md` and `proposal_zh.md`. Its project chapter
describes A0/B0 pretrained baselines and the four paired historical-state recovery
groups A-H/A-R/B-H/B-R. Both retain and reset branches receive the same correction.
Core model weights remain fixed; evidence can support at most one automatic-policy
validation. Teaching videos are not formal results.

Refreshing a report copies these two source texts (as `.md.txt`) and their
existing PDFs into the run's `proposal/` folder. It also offers the English
`proposal.tex` and two explicitly curated LaTeX downloads:

- `proposal-latex.zip`: `proposal.tex`, `references.bib`, `neurips_2026.sty`.
- `neurips-2026-template-files.zip`: retained `neurips_2026.tex`,
  `neurips_2026.sty`, `checklist.tex` from `templates/neurips`, repackaged without
  changing their current bytes. This is not the originally supplied ZIP.

The webpage explains the recorded 2024/2026 template-name discrepancy and
distinguishes the HTML reading view, formatted PDF, editable current source and
retained template example. `proposal/manifest.json` records source names, exact
byte counts, hashes and archive member inventories. Nothing is fetched from
GitHub or uploaded. To resync after changing the proposal, run:

```powershell
.venv/Scripts/python.exe -m learning.report --output outputs/learning/20261011-095748-9d89fd
```

This preserves the previous bilingual pages and does not rerun inference or
modify saved videos/measurements. The preview server also serves
the copied PDFs; directory traversal and arbitrary source serving remain blocked.

Each run contains:

- `index.html` / `index.en.html`: experiment overview, results, progress and next preparation tasks.
- `handbook.html` / `handbook.en.html`: full Chinese / English lessons, videos, frame-stepping controls and limitations, linked by the header language switch.
- `comparison.mp4`: synchronized four-panel view (same frame in each panel).
- `01_boxes.mp4`, `02_masks.mp4`, `03_bytetrack.mp4`, `04_sam2.mp4`: executed lesson videos. Missing lessons are clearly marked.
- `source.mp4`, `frames/`: the exact resized/JPEG-decoded input shared across models; audio is omitted.
- `sam2_prompt.jpg`, `sam2_prompts.json`: inspect exactly how objects entered SAM.
- `yolo_records.jsonl`, `sam2_records.jsonl`: per-frame boxes/classes/IDs or mask areas. These are educational logs, **not complete benchmark mask submissions**.
- Three sample binary masks per SAM object (first/middle/last frame), plus preview images.
- `summary.json`: source, parameters, versions, hashes, diagnostic timing and allocated GPU memory. Failed runs keep their status and error.
- `environment.txt`: installed-package snapshot.

YOLO-only and SAM-only runs are supported. Automatic SAM initialization with no first-frame detection produces a **partial** report, not fabricated tracking output; select an object manually or choose a different clip/category. Real inference errors return a nonzero exit code.

## Important scientific boundaries

- No ground-truth annotations are available for these demo videos. Do not report HOTA, IDF1, segmentation accuracy, or a model ranking from them. Mask IoU helpers/tests use toy masks only.
- The four-grid comparison is **pedagogical**, not a fair full-system benchmark: SAM gets at most the first-frame top-scoring objects, while YOLO/ByteTrack can discover later objects. IDs in the two methods are independent and are not expected to match numerically.
- This SAM lesson has **no periodic discovery, detection-to-track association, prompt refresh, retirement, or long-term re-identification**. Those are implementation tasks for the proposal's automatic pipeline, not hidden built-in SAM features.
- Frame loading is not future-prompt leakage: all prompts here are on frame 0 and propagation is forward-only. No future-frame prompts or annotations are supplied.
- The player uses the **source video frame rate**, not measured inference FPS. Per-model times include cold start and have different boundaries, so the report deliberately avoids a performance leaderboard. Peak PyTorch allocated memory is not total VRAM usage.
- Frames are downscaled (never upscaled), dimensions rounded to even values, and encoded as JPEG quality 95 once for every method. YOLO then uses `--imgsz`; SAM keeps its configured 1024 internal encoder size. This is not a claim of equal internal resolution.
- The small SAM 2.1 checkpoint is a model-size variant, not a separate lesson/model task. Tiny is the proposal's core version.

## SAM-Track / DeAOT background (outside the revised project scope)

This background method is **not installed or run** by the learning scripts. The October 15, 2026 proposal retains two automatic pipelines and four controlled retain/reset groups with fixed weights. DeAOT is not an additional project pipeline. The downloaded `DeAOTB_PRE_YTB_DAV.pth` alone is insufficient: SAM-Track also needs the original SAM checkpoint and its own compatible environment/integration. DeAOT propagates initialized masks; SAM-Track uses original SAM to initialize/discover objects and DeAOT to propagate them. Do not rename SAM 2 outputs as SAM-Track results.

Read [the background-method guide](../docs/model-guide/03-sam-track-and-deaot.md) and the [upstream SAM-Track repository](https://github.com/z-x-yang/Segment-and-Track-Anything) for context. This is not a third pipeline in the revised study.

## Dataset access and preparation

The project retains **YouTube-VIS 2021**, using the preprocessed Google Drive release linked by [SlotCurri](https://github.com/wjun0830/SlotCurri). The bilingual homepage, sidebar and experiment walkthrough link to `dataset.html` / `dataset.en.html`, containing audited counts, format explanations and real frame/mask inspection.

- [Google Drive archive](https://drive.google.com/file/d/1Iv-2zK6MnH0oDFTx9iBgQcPNh5PBzM7i/view?usp=sharing): downloaded `ytvis2021_resized.zip`, 28,377,138,264 bytes (26.43 GiB). The 2026-10-17 complete local audit checked all 114 TAR shards and all annotated arrays: 2,985 videos, 300 annotated, 2,685 RGB-only; five target classes cover 226 distinct videos. Counts by class are imbalanced (only six cat videos).
- The documented training export is video-only. Use the annotated export containing `segmentations.npy` for scoring; preserve within-video instance channels and verify category IDs, frame order, annotation timing and resizing.
- The distribution's validation portion is an internal split of the original labeled training data. Repartition its annotated data for this project. The initial seed-550 allocation needs coverage adjustments (horses otherwise only in development); a feasible 120/40/40 allocation exists, but the formal split is not frozen. Original FPS, timestamps and frame filenames are absent, so exported steps are not seconds or guaranteed consecutive source frames.
- Convert WebDataset shards to frames and YTVIS-format JSON under `data/raw/youtube_vis_2021/`, then use the manifest helper described in [data/README.md](../data/README.md). The current teaching runner accepts local video files; benchmark-format conversion remains separate implementation work.

The [official YouTube-VIS page](https://youtube-vos.org/dataset/vis/) remains the original dataset reference. No dataset download or conversion is performed by refreshing the teaching website.

### Real-data frame viewer

The default export includes five annotated videos (2686 person, 2744 dog, 2689 cat, 2718 horse, 2692 car), 207 frames. RGB PNGs preserve array pixels/dimensions; white/transparent per-channel PNG masks encode `segmentations > 0`. The curated manifest retains category IDs, channel identities, per-frame areas and archive provenance. Colors identify channels, not categories. The viewer provides synchronized RGB/GT, previous/next/range/play controls, single-channel isolation, overlay/binary modes, language-state preservation and offline/no-JavaScript fallback. It performs no inference.

```powershell
# Only needed when preparing/rebuilding sample assets, after the complete audit:
.\.venv\Scripts\python.exe -m tracking_lab.prepare --archive data/raw/youtube_vis_2021_slotcurri/ytvis2021_resized.zip --audit data/raw/youtube_vis_2021_slotcurri/audit/audit.json --output experiments/data/stage1
# Refresh pages only; does not re-export samples or touch model/video results:
.\.venv\Scripts\python.exe -m learning.report --output outputs/learning/20261011-095748-9d89fd
```

Sample assets and the source archive remain local and Git-ignored. The existing read-only website serves only the curated PNG previews, not the full dataset archive. This work does not alter the formal proposal or benchmark split manifest.

## Sources and licenses

### Real experiment results in the same site

`results.html` and `results.en.html` integrate the verified local pilot into the existing 8765 learning website. Both homepages link from the first-screen actions and sidebar. They reuse the site's theme, page navigation and bilingual header; language switching preserves the selected video/frame. The original 8770 pilot preview has been stopped and is not the normal workflow.

Import only saved, completed results with a passing verification record:

```powershell
.\.venv\Scripts\python.exe -m learning.pilot_page --source outputs/pilot/stage1-20261017-3080-verified --output outputs/learning/20261011-095748-9d89fd
```

The importer copies an allowlist of figures, videos, source snapshots and JSON into `pilot-results/`; it excludes raw NPZ masks, arbitrary files and absolute host paths from summary metadata. It does not rerun models or change source predictions/scores. Normal `learning.report` refreshes retain the integrated results and back up both page languages. Website source is tracked; imported result assets and generated pages remain Git-ignored, without a separate deployment.

Actual runtime code, data auditing/preparation and scientific tests now live in `experiments/`. The website importer computes its own file hashes and does not import experiment inference code. The old dataset export/audit implementations were moved out entirely; new data preparation uses `tracking_lab.prepare` / `tracking_lab.audit`. Existing website sample assets stay in place for display, but inference defaults to the separate `experiments/data/stage1/` copy. To display a newly finished run, pass its `experiments/runs/<run>` path to the importer; no experiment imports or starts this website.

- [Ultralytics tracking API](https://docs.ultralytics.com/modes/track/) and [ByteTrack](https://github.com/ifzhang/ByteTrack).
- [Meta SAM 2](https://github.com/facebookresearch/sam2) and [installation notes](https://github.com/facebookresearch/sam2/blob/main/INSTALL.md).
- [Official PyTorch wheel combinations](https://pytorch.org/get-started/previous-versions/).

Respect upstream software/checkpoint licenses and each dataset's terms. This learning code does not relicense downloaded models, source code, or videos. No credentials are required or stored by these lessons.

### Long-window recovery follow-up

`recovery.html` / `recovery.en.html` retain the reviewed eight-step H/R pilot.
`recovery-long.html` / `recovery-long.en.html` follow the same rider/cat events
for 30 steps, compare 8/20/30 checkpoints and separate the skip-one-refresh
ablation from the main experiment. The homepage's latest-results action opens
the follow-up; baseline, protocol, program map and run records link to both.

```powershell
.\.venv\Scripts\python.exe -m learning.recovery_long_data --study experiments/runs/recovery-long-20261020-study --output outputs/learning/20261011-095748-9d89fd
.\.venv\Scripts\python.exe -m learning.report --output outputs/learning/20261011-095748-9d89fd
```

The importer requires the prior eight-step manifest, corrected-baseline identity,
complete/repeated runs, source snapshots, video fingerprints and checkpoint
agreement with saved curves. It validates before copying an allowlist into
`recovery-long-results/`, excludes raw masks/private summary paths and refuses
different archived evidence. CSVs use exact-byte `.csv.txt` aliases with CSV
download names because the existing server does not serve `.csv`. No new server,
model inference, cloud deployment or Git synchronization is involved.
