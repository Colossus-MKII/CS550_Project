# Robust Multi Object Segmentation and Tracking with SAM 3

**Jingdi Wu, Yupu Guo, Christina Ross**  
Rutgers University · CS550 Massive Data Mining · Fall 2026  
Project proposal · October 7 2026

## Abstract

We propose a controlled study of automatic instance segmentation and tracking across diverse object categories, including people and animals. We will compare pretrained SAM 3 with YOLO segmentation coupled to ByteTrack and BoT-SORT, and test whether limited supervised adaptation improves mask accuracy, identity continuity, and robustness. SAM 3 adaptation will target its image and detection stage while retaining the temporal tracker, subject to a GPU feasibility pilot. A smaller YOLO fine-tuning experiment provides a fallback. The study will use annotated videos, fixed evaluation splits, standard metrics, and paired robustness tests. Deliverables include reproducible code, an eight-page report excluding references, and an in-class presentation.

## 1 Motivation and Research Questions

Objects in videos change position, appearance, and visibility. Accurate outlines in individual frames do not guarantee that the same object keeps its identity through occlusion. We will examine these interacting errors across several categories, rather than treating vehicle tracking as the only application.

Our questions are: (RQ1) How do SAM 3 and lightweight segmentation-plus-association pipelines trade mask accuracy, identity continuity, and computation? (RQ2) Does dataset-specific fine-tuning improve those measures on unseen videos? (RQ3) How sensitive are the methods to image degradation and challenging motion? We hypothesize that adaptation improves segmentation, but association may remain a bottleneck. This is a hypothesis to test, not an expected result presented as fact.

## 2 Methods and Adaptation

SAM 3 detects and segments instances matching a text concept and tracks them through video [1]. We will use fixed category names without manual test-time corrections. YOLO predicts per-frame masks; ByteTrack and BoT-SORT associate detections into tracks [2-4]. The core pretrained comparison comprises SAM 3, YOLO11s-seg with ByteTrack, and the same YOLO checkpoint with BoT-SORT. We will document camera compensation and appearance matching settings. Each method must output instance masks, category labels, confidence scores, and persistent identities.

Fine-tuning will use only training frames and instance masks. The official SAM 3 training guide documents single-GPU execution, but supplies image-stage examples rather than a ready end-to-end video-tracker training recipe [1]. Its example configuration disables segmentation by default; we must enable and verify mask supervision. If the pilot succeeds, we will adapt the image detector and shared features, preserve tracker weights, and verify checkpoint loading into the video pipeline. We will compare the same SAM 3 variant before and after adaptation. This experiment measures the effect of image-stage adaptation on video performance.

If SAM 3 adaptation exceeds the available memory, allocation, or integration budget, we will fine-tune YOLO and evaluate both association methods. Tracker threshold adjustment is configuration tuning, not learned-weight fine-tuning. SAM 3 remains a pretrained comparator if inference fits. Video-tracker training and custom LoRA are outside the planned scope.

## 3 Data and Fair Comparison

We will use a manageable subset of YouTube-VIS 2021, which provides masks and identities for multiple object categories [5]. The initial target is up to 200 labeled videos spanning five categories shared with YOLO, such as person, dog, cat, horse, and car. Final class and instance counts will be reported after data inspection. We will partition labeled training videos into 60 percent training, 20 percent validation, and 20 percent held-out evaluation, keeping complete source videos together and maintaining category coverage.

A single versioned split manifest will control all experiments. Training-frame sampling will reduce near-duplicate examples; evaluation will retain the annotated temporal sequence. We will map category definitions consistently and follow annotation ignore rules. Test masks will be used only for evaluation. SAM 3 text prompts will use fixed category names, not ground-truth boxes or masks. We will record native preprocessing, checkpoint versions, and upstream commits. Selected categories define the evaluated recognition task; arbitrary unseen-category performance is a separate question.

## 4 Evaluation and Stability

The primary score is video AP on our held-out subset using the official YouTube-VIS evaluator, measuring classified mask tracks across frames [5]. Per-frame mask AP diagnoses segmentation. Mask-based HOTA, its detection/association components, and ID switches require a validated conversion and matching protocol [6]. These are supplementary analyses, not challenge results. SAM 3 will run each category concept separately with namespaced IDs; validation will fix overlap conflicts and track-confidence aggregation. Timing includes all category runs, decoding, preprocessing, inference, and association; we record hardware, precision, resolution, and peak GPU memory.

We define stability as identity continuity and resistance to input degradation. Paired tests will apply predefined mild blur, brightness changes, and JPEG compression to held-out frames without changing geometry. We will report each method's score drop from clean input, with results by category and, where enough examples exist, object size and occlusion. Natural disappearance and reappearance cases will support qualitative recovery analysis. Raw overlap between adjacent predicted masks is not a stability score because genuine motion changes mask position and shape. Bootstrap intervals will resample whole videos; multiple training seeds will be used if the allocation permits.

## 5 Compute Feasibility and Work Plan

Lab GPU availability is not yet confirmed. The official SAM 3 guide allows local single-GPU training but does not specify a universal VRAM minimum or duration [1]. We will first record GPU memory, CUDA compatibility, storage, and job limits; obtain checkpoint access; run approximately 100 frames of video inference; and run at least 20 optimizer steps with batch size one and mask supervision. The pilot must complete within the allocation with memory headroom, nonzero mask loss, finite gradients, changed intended parameters, and a correctly reloaded checkpoint. Measured throughput will determine the training budget. No GPU-hour estimate will be treated as established before this pilot.

Weeks 1-2 will finalize the proposal, dataset split, environment, pretrained baselines, and evaluator. Weeks 3-4 will complete the compute pilot, adaptation, and validation. Week 5 will freeze settings and run held-out comparisons. Week 6 will analyze robustness and failures. Weeks 7-8 will produce and revise the report, release reproducible configurations, and prepare the presentation. If the pilot fails, the YOLO adaptation path will begin by the end of week 3.

The report will cover related work, data and methods, quantitative comparisons, failure cases, and limitations. We will release reproducible scripts, configurations, split manifests, and result schemas. Data and weights remain external; improvement claims require measured evidence.

## References

1. Meta AI. SAM 3 code, model documentation, and training guide. 2026. [Repository](https://github.com/facebookresearch/sam3); [training guide](https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md); [example configuration](https://github.com/facebookresearch/sam3/blob/main/sam3/train/configs/roboflow_v100/roboflow_v100_full_ft_100_images.yaml).
2. Ultralytics. Instance segmentation and multi-object tracking documentation. 2026. [Segmentation](https://docs.ultralytics.com/tasks/segment/); [tracking](https://docs.ultralytics.com/modes/track/).
3. Zhang et al. ByteTrack Multi-Object Tracking by Associating Every Detection Box. ECCV 2022. [Paper](https://arxiv.org/abs/2110.06864).
4. Aharon, Orfaig, and Bobrovsky. BoT-SORT Robust Associations Multi-Pedestrian Tracking. 2022. [Paper](https://arxiv.org/abs/2206.14651).
5. Yang, Fan, and Xu. Video Instance Segmentation. ICCV 2019; YouTube-VIS 2021 dataset and evaluation documentation. [Dataset](https://youtube-vos.org/dataset/vis/).
6. Luiten et al. HOTA A Higher Order Metric for Evaluating Multi-Object Tracking. IJCV 2020; TrackEval implementation. [Paper](https://arxiv.org/abs/2009.07736); [code](https://github.com/JonathonLuiten/TrackEval).
