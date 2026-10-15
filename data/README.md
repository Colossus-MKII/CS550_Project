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

The README advertises a 26.43 GB download. The archive has not been downloaded or inspected here; its actual contents and usable counts must be verified before fixing the experimental subset.

The upstream [preparation script](https://github.com/wjun0830/SlotCurri/blob/main/data/save_ytvis2021.py) and [configuration](https://github.com/wjun0830/SlotCurri/blob/main/configs/slotcurri/ytvis2021.yaml) document the expected layout:

- Resized WebDataset `.tar` shards under `ytvis2021_resized`, with a default short side of 320 pixels. The configuration names 84 training shards and 30 validation shards; these are expected paths, not a verified archive inventory.
- The documented training command uses `--only-videos` and exports `video.npy` without masks. The validation command includes `segmentations.npy` with shape `(F, H, W, num_obj)`; each object's channel contains its mask multiplied by its category ID.
- The current script derives both parts from the original labeled training data and reserves its final 300 video IDs for validation. This is an internal split, not the official challenge validation split; confirm that the downloaded release matches the script before relying on these counts.
- Sample keys preserve source video IDs. Instance channels provide within-video correspondence, but original annotation IDs and frame filenames are not explicitly exported. Preserve channel identity during conversion, verify categories and frame ordering, and record the preprocessing and source mapping.

Use the annotated portion for scored experiments. The target of 200 videos covering all five categories remains provisional until label availability and category counts are checked. The video-only portion can support inference smoke tests but cannot supply ground truth for MOTS evaluation.

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
