# Eight-Page Final Report Plan

The chapter 1 slides require an eight-page final report excluding references. Use the official ACML conference-track class preserved in [templates/acml](../templates/acml/README.md), as selected for this project. Start from [paper/proposal.tex](../paper/proposal.tex) and preserve its single-column typography and geometry. The allocation below is a writing plan; adjust it once the actual results show which findings need space.

| Pages | Content | Evidence to prepare |
| --- | --- | --- |
| 1 | Abstract, problem, motivation, research questions, and contributions | Explain why mask accuracy and identity continuity are different; define the automatic prompt policy and the tested object categories. |
| 2 | Related work and method comparison | Contrast segmentation plus association with SAM 3 concept-based video segmentation. Explain ByteTrack and BoT-SORT settings and the exact adaptation scope. |
| 3 | Dataset, splits, annotation mapping, and evaluation | Include per-split/category counts, sequence-disjoint split rules, video AP, and the verified supplementary matching protocol. |
| 4 | Implementation and compute pilot | State checkpoints, upstream revisions, training settings, mask-supervision checks, checkpoint-transfer verification, and measured hardware costs. If SAM 3 adaptation fails, explain the measured reason and the YOLO fallback. |
| 5 | Clean-input quantitative comparison | Present pretrained and adapted results with video-level uncertainty where feasible. Compare mask performance, identity continuity, FPS, and memory without inventing missing measurements. |
| 6 | Robustness and controlled comparisons | Show paired drops under blur, brightness change, and JPEG compression. Separate changing the segmenter weights from changing the tracker. |
| 7 | Qualitative analysis and failures | Show consistently colored track IDs through occlusion/reappearance, mask errors, category errors, and identity switches on shared clips. Include failures as well as successes. |
| 8 | Discussion, limitations, and conclusion | Answer each research question from the evidence. Discuss dataset coverage, pretraining overlap, annotation limitations, GPU budget, and remaining work. |

References follow the eight main pages. Do not spend a full page on a title cover.

## Minimum evidence for a complete project

- Three pretrained pipelines on one frozen, annotated video subset, if SAM 3 inference is available.
- One validated adaptation path: SAM 3 image-stage adaptation when its gate passes, otherwise YOLO segmentation fine-tuning.
- Official video AP on the same internal held-out sequences; runtime and memory measured with a stated timing scope.
- Paired clean/corrupted evaluations and representative identity-continuity failures.
- Reproducible split/configuration/checkpoint provenance and an honest account of incomplete supplementary evaluations.

Treat mask HOTA and additional training seeds as secondary milestones if their integration threatens the core comparison. The final report should clearly separate performed experiments, observed results, and untested future work.

## Tables and figures to collect

1. Dataset counts by split and category.
2. Model/checkpoint, trainable components, prompts, tracker settings, GPU, and input resolution.
3. Clean-input video AP, supplementary metrics when verified, FPS, and peak VRAM.
4. Clean-to-corrupted score changes for each pipeline.
5. Before/after adaptation results under unchanged tracker settings.
6. A short sequence figure with the same frames and colors for every method.

Create these from actual experiment logs. Empty result templates are not measured evidence.
