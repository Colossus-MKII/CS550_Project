# Robust Multi-Object Segmentation and Tracking

**Jingdi Wu, Yupu Guo, Christina Ross**  
Rutgers University · CS550 Massive Data Mining · Fall 2026  
Project proposal · October 7 2026 · ACML conference-track template

## Abstract

We compare automatic segmentation and tracking across people, animals, and vehicles using SAM 3 and YOLO with ByteTrack or BoT-SORT. We test whether adaptation improves mask accuracy, identity continuity, and robustness on annotated, sequence-disjoint videos. SAM 3 image-stage fine-tuning requires a GPU and mask-training pilot; YOLO adaptation provides a fallback. Deliverables are reproducible code, an eight-page report excluding references, and a presentation.

**Keywords:** video instance segmentation; multi-object tracking; fine-tuning; robustness

## 1 Introduction

Accurate masks do not ensure identity continuity through motion or occlusion. We ask how methods trade accuracy, association, and computation; whether adaptation improves unseen-video performance; and how degradation affects these measures. We hypothesize that adaptation improves masks while association may remain a bottleneck.

## 2 Methods and Adaptation

SAM 3 tracks instances matching a text concept (Meta AI, 2026). Baselines use YOLO11s-seg with ByteTrack or BoT-SORT (Ultralytics, 2026; Zhang et al., 2022; Aharon et al., 2022). Each outputs masks, categories, confidence, and IDs. SAM 3 uses fixed prompts without manual corrections; separate concept runs use namespaced IDs and validation-selected conflict handling. Timing includes every run.

If feasible, we adapt SAM 3's image detector and shared features, holding its tracker fixed. Its example configuration disables segmentation; mask supervision and checkpoint transfer must be verified. Otherwise, we fine-tune YOLO with both trackers, retaining pretrained SAM 3 when inference fits. Threshold selection is configuration tuning. Custom LoRA and tracker training are outside scope.

## 3 Data and Experimental Protocol

We target up to 200 labeled YouTube-VIS 2021 training videos covering person, dog, cat, horse, and car (Yang et al., 2019), split 60/20/20 by complete source video with category coverage. Training uses sampled frames and masks; evaluation retains annotated sequences. We freeze splits, category mappings, prompts, checkpoints, preprocessing, and tracker settings. Test annotations serve only scoring; annotation limitations and known pretraining overlap will be disclosed.

## 4 Evaluation and Robustness

Primary evaluation is held-out video AP using the official YouTube-VIS evaluator. Frame mask AP diagnoses segmentation. Supplementary mask HOTA, DetA, AssA, and ID switches require validated annotation conversion and matching (Luiten et al., 2020). These are internal subset results. Validation fixes track-confidence aggregation.

Paired blur, brightness, and JPEG tests preserve geometry. We report score drops, identity continuity, occlusion failures, FPS, and peak GPU memory, recording hardware, precision, resolutions, and timing scope. Uncertainty resamples videos; repeated seeds depend on budget. Adjacent-mask overlap cannot measure stability because objects move.

## 5 Feasibility and Work Plan

Hardware is unconfirmed. SAM 3 supports single-GPU image-stage training without a universal memory guarantee. A 100-frame inference and 20-step mask-training pilot at batch size one must verify memory headroom, finite gradients, changed intended parameters, and reloaded weights. Measured throughput sets the training budget.

Weeks 1-2 establish data, baselines, and evaluation; weeks 3-4 cover the pilot and adaptation; week 5 runs frozen held-out comparisons; week 6 analyzes robustness; weeks 7-8 prepare the report and presentation. YOLO fallback begins by week 3. Improvement claims require measured evidence.

## References

Aharon, Orfaig, and Bobrovsky. BoT-SORT: Robust Associations Multi-Pedestrian Tracking. 2022. [Paper](https://arxiv.org/abs/2206.14651).

Luiten et al. HOTA: A Higher Order Metric for Evaluating Multi-Object Tracking. IJCV, 2020. [Paper](https://arxiv.org/abs/2009.07736); [implementation](https://github.com/JonathonLuiten/TrackEval).

Meta AI. SAM 3 model and training documentation. 2026. [Repository](https://github.com/facebookresearch/sam3); [training guide](https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md).

Ultralytics. Segmentation and tracking documentation. 2026. [Segmentation](https://docs.ultralytics.com/tasks/segment/); [tracking](https://docs.ultralytics.com/modes/track/).

Yang, Fan, and Xu. Video Instance Segmentation. ICCV, 2019. [YouTube-VIS dataset](https://youtube-vos.org/dataset/vis/).

Zhang et al. ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV, 2022. [Paper](https://arxiv.org/abs/2110.06864).
