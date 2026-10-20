# Video data

This directory separates small smoke-test videos from the labeled YouTube-VIS 2021 data used by the project experiments.

## Pilot videos

Run the resource downloader from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1 -Videos
```

It downloads the five small videos distributed with Meta's official SAM 2 demo into `data/pilot/videos/`. These files are useful for installation and inference smoke tests, but they are **not** the evaluation dataset and do not include YouTube-VIS ground truth.

## YouTube-VIS 2021 (via SlotCurri Google Drive release)

The proposal retains YouTube-VIS 2021. Because the team could not complete CodaLab registration, the planned access route is the preprocessed Google Drive release linked by **SlotCurri** (Moon et al., 2026). SlotCurri supplies this distribution; it is not the original dataset creator.

- Repository: <https://github.com/wjun0830/SlotCurri>
- Google Drive archive (`ytvis2021_resized.zip`, 26.43 GB): <https://drive.google.com/file/d/1Iv-2zK6MnH0oDFTx9iBgQcPNh5PBzM7i/view?usp=sharing>

The archive was downloaded and fully audited locally on October 17, 2026: 28,377,138,264 bytes (26.43 GiB), SHA-256 `b0708de42d7f7277998527fb23098062039323c4043d62d83d2146d2444d2d20`. All 114 TAR shards passed CRC checks. There are 2,985 distinct videos: 2,685 RGB-only and 300 with aligned RGB/mask arrays. The five target classes cover 226 distinct annotated videos; category counts overlap (person 198, dog 17, cat 6, horse 12, car 33). Coverage is sufficient to select 200, but highly imbalanced. The coverage-constrained seed-550 split is now frozen in `experiments/manifests/ytvis2021-200-seed550-v1.json`: 120 development / 40 validation / 40 evaluation IDs. The original five pilots stay in development; automatically screened duplicate groups stay together. The 200 IDs represent 198 screened visual groups, not 200 proven independent source recordings.

The [independent experiment workspace](../experiments/README.md) and [code guide](../experiments/CODE_GUIDE.md) describe the first five-video run and its data adapter. Runtime inputs now live under `experiments/data/stage1/`, outside the teaching website. They are lossless PNG exports of actual RGB arrays and mask foregrounds, not the unlabeled teaching videos. `experiments/tracking_lab/defaults/stage1_selection.json` fixes the development-pilot IDs; exclude these from the future held-out evaluation split. Original source timestamps, FPS, annotation IDs and frame filenames are absent from this release, so temporal measurements initially use exported steps rather than seconds. Formal benchmark-format conversion and the final split manifest remain separate tasks.

The upstream [preparation script](https://github.com/wjun0830/SlotCurri/blob/main/data/save_ytvis2021.py) and [configuration](https://github.com/wjun0830/SlotCurri/blob/main/configs/slotcurri/ytvis2021.yaml) document the expected layout:

- Resized WebDataset `.tar` shards under `ytvis2021_resized`, with a 320-pixel short side. The audit confirms the configured 84 training and 30 validation shards; all annotated samples have the expected short side.
- The documented training command uses `--only-videos` and exports `video.npy` without masks. The validation command includes `segmentations.npy` with shape `(F, H, W, num_obj)`; each object's channel contains its mask multiplied by its category ID.
- The current script derives both parts from the original labeled training data and reserves its final 300 video IDs for validation. This is an internal split, not the official challenge validation split; confirm that the downloaded release matches the script before relying on these counts.
- Sample keys preserve source video IDs. Instance channels provide within-video correspondence, but original annotation IDs and frame filenames are not explicitly exported. Preserve channel identity during conversion, verify categories and frame ordering, and record the preprocessing and source mapping.

Use the annotated portion for scored experiments. The complete audit establishes 226 five-class candidates. The frozen split is distinct from the manually reviewed 16-event development cohort (`independent-events-review-20261020-v3.json`): four events each for stable controls, motion changes, detection competition and occlusion. Video 2967 is retained only as an unrun boundary case. This cohort has person/car/dog events, not a balanced five-class benchmark. Validation/evaluation predictions have not been used for event exploration. The video-only portion can support inference smoke tests but cannot supply ground truth for MOTS evaluation.

After converting annotated shards to frames and YTVIS-format JSON, place them under:

```text
data/raw/youtube_vis_2021/
  train/
    JPEGImages/          # extracted video frames
  instances_train.json   # COCO/YTVIS-format annotations
```

Do not commit the dataset. `data/raw/` is ignored by Git.

After extraction/conversion, create a reproducible, video-level pilot split for the five proposal categories:

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
