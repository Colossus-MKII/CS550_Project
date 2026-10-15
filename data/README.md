# Video data

This directory separates small smoke-test videos from the labeled YouTube-VIS 2021 data used by the project experiments.

## Pilot videos

Run the resource downloader from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1 -Videos
```

It downloads the five small videos distributed with Meta's official SAM 2 demo into `data/pilot/videos/`. These files are useful for installation and inference smoke tests, but they are **not** the evaluation dataset and do not include YouTube-VIS ground truth.

## YouTube-VIS 2021

The proposal fixes the experimental dataset to YouTube-VIS 2021. Its official page is:

- <https://youtube-vos.org/dataset/vis/>
- Official 2021 CodaLab download: <https://codalab.lisn.upsaclay.fr/competitions/7680>

CodaLab requires a signed-in account and acceptance of its participation/usage terms, so the archive is not downloaded by the unattended resource script. Download the 2021 training archive and annotations from the official competition page, then extract them under:

```text
data/raw/youtube_vis_2021/
  train/
    JPEGImages/          # exact archive layout may include another train subdirectory
  instances_train.json   # use the actual extracted filename/path
```

Do not commit the dataset. `data/raw/` is ignored by Git.

After extraction, create a reproducible, video-level pilot split for the five proposal categories:

```powershell
python tools/select_ytvis_subset.py `
  --annotations data/raw/youtube_vis_2021/instances_train.json `
  --output data/manifests/ytvis2021_subset.json `
  --max-videos 200 `
  --seed 550
```

The selector uses whole videos, targets `person`, `dog`, `cat`, `horse`, and `car`, and creates deterministic 60/20/20 train/validation/evaluation assignments. It writes a manifest only; it does not duplicate frames.

Under the October 15 proposal, the helper's 120-video `train` partition serves as the development partition: the core study keeps model weights fixed. Use the 40 validation videos to diagnose A0/B0 failures and fix recovery-event selection, thresholds, windows, and any evidence-supported follow-up policy. Reserve the 40 evaluation videos for final testing with these choices frozen. Verify category counts, source-video grouping and the final manifest before tuning.

The planned recovery study samples events from these same partitions. Record video, target, event type, correction frame, box source, subsequent evaluation timestamps, and eligibility in an event manifest. Select events without looking at which retain/reset strategy wins. The main four-group comparison uses events where both pipelines retain usable target state; separately count events with already-deleted tracks. Check annotation density and enough post-correction observations before freezing the event rules.

Full automatic A0/B0 inference does not receive annotations or ground-truth target routing. Controlled recovery experiments explicitly supply the target correspondence and separately compare actual YOLO boxes with reference boxes derived only from the correction frame's annotations. Future annotations are for scoring only. These diagnostic results must remain separate from automatic-system scores. After the correction, each pair continues with identical normal input schedules and no additional annotation corrections.

Before experiments, verify that every path in the generated manifest exists and inspect the per-category counts. The subset helper creates a video manifest; it does not yet create recovery events or implement the paired experiments.
