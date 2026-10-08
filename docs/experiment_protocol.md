# Experiment Protocol

## Task

Automatically detect, outline, and track instances of the selected object categories in videos. Temporary stops do not remove an instance from evaluation. Physical moving-versus-stationary classification is not an annotation requirement of this protocol.

## Core configurations

| ID | Model and association | Status |
| --- | --- | --- |
| S0 | Pretrained SAM 3 with fixed category text prompts and its video tracker | Required comparison if documented CUDA inference is available |
| Y0 | Pretrained YOLO11s segmentation with ByteTrack | Baseline |
| Y1 | Same pretrained YOLO11s segmentation with BoT-SORT | Baseline |
| S1 | Adapted SAM 3 image detector and shared features with temporal tracker held fixed | Conditional on compute and checkpoint-transfer pilot |
| Y2 | Fine-tuned YOLO11s segmentation with ByteTrack | Adaptation fallback |
| Y3 | Same fine-tuned YOLO11s segmentation with BoT-SORT | Adaptation fallback |

Use one model variant before and after adaptation. Define categories and prompt wording once from training/validation data. Use the same source videos and annotation frequency for all methods; record each method's native preprocessing and internal image size. Do not describe different internal resolutions as a matched-resolution experiment.

## Data

Use a versioned subset of labeled YouTube-VIS 2021 training videos. Initial target: up to 200 videos and five shared categories, with category coverage checked before freezing the manifest. Split by full source video into training, validation, and held-out evaluation; intended proportions are 60/20/20. Never put neighboring frames from one video into different splits. Group duplicate source clips when source identity is available.

Report videos, frames, object instances, and masks per split and category. Document taxonomy mappings, missing annotations, and supported ignore rules. Check annotation completeness and disclose limitations; the official evaluator does not automatically excuse arbitrary unannotated objects. Images for supervised training require instance masks. Retain sequence IDs and persistent object IDs for video evaluation.

## Evaluation

The primary score is YouTube-VIS video AP on the project's held-out subset using the official evaluator. This internal five-category split is not an official challenge result. Export a category label and a confidence per predicted mask track, with a documented track-confidence aggregation rule fixed on validation data. The starter uses the mean confidence over detected frames; confirm this rule for every pipeline and note that confidence scales differ. Use official spatiotemporal mask IoU and annotation rules. Per-frame mask AP is a supplementary segmentation diagnostic.

For SAM 3, run each category concept separately and namespace object IDs by category/session. If two concepts predict the same instance, fix a deduplication and category-conflict rule using validation videos before evaluation. Record its threshold and include every concept run plus merging in total runtime. This procedure must be implemented and verified in the pending SAM 3 adapter; do not treat separate category sessions as one free multi-category pass.

Mask-based HOTA, DetA, AssA, and identity-switch measurements are supplementary analyses. Validate the annotation conversion and evaluator on a tiny known sequence before measuring models. These scores are not a replacement for the official VIS protocol. The starter repository does not claim that its canonical prediction JSONL is already an official submission format.

## Robustness

Run clean video, Gaussian blur, brightness change, and JPEG re-encoding with predefined parameters. Preserve geometry so existing ground-truth masks remain aligned. Compare paired changes on the same held-out videos. Report settings and clean-to-corrupted score differences; do not use test corruption results to choose training augmentation.

Inspect naturally occluded and reappearing objects. Measure identity continuity and demonstrate representative failures. Any recovery-time definition must specify visibility, overlap threshold, sampling frequency, and identity matching. Adjacent-mask IoU without motion compensation is not a measure of temporal stability.

## Reproducibility

Fix split seed, prompt names, category mapping, checkpoint variant, upstream commits, tracker settings, preprocessing, training-frame sampling, and evaluation versions. Use validation data for selection and leave the final split untouched until settings are frozen. Report repeated training seeds when affordable. Estimate confidence intervals by resampling videos, not individual neighboring frames.

Record end-to-end runtime, warm-up, hardware, precision, batch size, peak GPU memory, and whether rendering and output encoding are included. Store experiment metadata alongside masks and identities. No example result file in this repository represents measured benchmark performance.
