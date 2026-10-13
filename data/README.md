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

Under the October 13 proposal, 120 training videos support the prioritized, feasibility-gated YOLO adaptation study. The pretrained minimum deliverable uses 40 validation and 40 evaluation videos. Split whole videos before sampling temporally spaced training frames, retain all target instances, and use validation data to select the adapted checkpoint shared by A1/B1. Verify category counts, check identifiable source-video overlap across splits, and freeze the final manifest before tuning. No evaluation data may enter training or checkpoint selection, and no evaluation-set ground-truth prompts are allowed.

Before training, verify that every path in the generated manifest exists and inspect the per-category counts. The full experiment must use the labeled YouTube-VIS videos rather than the unannotated pilot clips.
