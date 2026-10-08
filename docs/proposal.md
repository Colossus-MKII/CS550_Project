# Evaluating Multi Object Segmentation and Tracking

**Jingdi Wu, Yupu Guo, Christina Ross**  
Rutgers University · CS550 Massive Data Mining · Fall 2026  
Project proposal · October 7 2026 · ACL conference template

## Abstract

We propose to compare four families of video instance segmentation and tracking methods across people, animals, and vehicles: YOLO segmentation with ByteTrack or BoT-SORT, SAM 2.1, SAM-Track, and OpenCV background subtraction. We will evaluate pretrained and adapted variants using mask accuracy, identity association, robustness, and computational cost. The study distinguishes neural fine-tuning from configuration and background adaptation. Deliverables are a reproducible comparison and an eight-page final report excluding references.

## 1 Research Questions

Accurate outlines do not guarantee consistent identities through motion, occlusion, or reappearance. We ask which pipelines best balance segmentation, detection, and association; whether fine-tuning improves unseen-video performance; and how camera motion and image degradation affect these results. Vehicles are one example among several categories. Tracking annotated objects does not itself identify physical motion relative to the world.

## 2 Methods and Adaptation

We will evaluate YOLO11s-seg with ByteTrack and BoT-SORT separately (Ultralytics, 2026); SAM 2.1 with temporal memory (Meta AI, 2026); SAM-Track using SAM keyframe masks and DeAOT propagation with periodic discovery (Cheng et al., 2023); and MOG2 and KNN as separate OpenCV baselines (OpenCV, 2026). Background masks require instance separation and a fixed association algorithm to obtain IDs.

Automatic SAM pipelines will use one frozen YOLO detector for box prompts, category labels, and new-object initialization at a validation-selected interval. The same detector will label and help separate foreground components for OpenCV; mask-IoU association will link its instances. These are detector-assisted pipelines, and runtime includes this dependency. YOLO retains native detection and association. No automatic run receives test ground-truth prompts or detector tracking IDs. Any ground-truth-initialized propagation study will be reported separately.

We plan pretrained-versus-fine-tuned pairs for YOLO's segmenter, SAM 2.1, and SAM-Track's DeAOT component, keeping SAM fixed for the latter (Yang and Yang, 2022). YOLO adaptation is required; SAM 2.1 and DeAOT training depend on GPU pilots and custom-data integration. OpenCV receives validation-tuned thresholds, history, and learning rates, with online background updates. These updates and tracker/discovery parameter tuning are not neural fine-tuning. Each weight comparison holds prompts, detector, association settings, and preprocessing fixed where applicable.

## 3 Data and Fair Evaluation

We target up to 200 labeled YouTube-VIS 2021 training videos containing person, dog, cat, horse, and car, split 60/20/20 by complete source video with category coverage (Yang et al., 2021). YOLO uses sampled mask-labeled images; temporal models require annotated clips. Methods process the same frozen timeline. We document target classes, annotation coverage, pretraining overlap, and fixed-versus-moving-camera strata. Moving-camera results are a stress test for background subtraction. Training and configuration selection use only training and validation videos.

Predictions contain original-resolution masks, categories, and persistent IDs. We validate category mapping, absent frames, ignore handling, and a shared overlap-resolution rule before annotation conversion. Results are an internal subset comparison, not official leaderboard scores.

## 4 Metrics and Robustness

Primary measures are sMOTSA and mask-based HOTA with DetA and AssA (Voigtlaender et al., 2019; Luiten et al., 2020). sMOTSA rewards matched-mask IoU while penalizing false positives and identity switches; HOTA separates detection and association quality. Diagnostics include MOTSA, MOTSP, mask-matched IDF1, ID switches, and false positives/negatives. MOTSP describes matched masks only. MOTS matching uses mask IoU greater than 0.5 and non-overlapping instances; HOTA uses its standard threshold sweep. We will validate a multicategory adapter rather than reuse a car/pedestrian-only loader unchanged. These are MOTS-style metrics on YouTube-VIS; native video AP is supplementary.

Paired blur, brightness, and JPEG tests preserve ground-truth geometry. We compare score drops, occlusion failures, FPS, peak GPU memory, and training time. Video-level bootstrap intervals quantify uncertainty where feasible. Timing includes prompting, discovery, and postprocessing. Adjacent-frame mask overlap alone cannot measure stability because objects move.

## 5 Feasibility and Schedule

GPU access is unconfirmed. Each neural candidate receives a 100-frame inference and 20-step training pilot to check memory, gradients, checkpoint reloads, and projected GPU hours. We start with smaller checkpoints and explicit trainable components. Inference and training failures will be documented, with pretrained-only comparisons where inference fits.

Weeks 1-2 establish data, adapters, and baseline families; weeks 3-4 cover tuning and feasible neural adaptation; weeks 5-6 run frozen evaluations and robustness tests; weeks 7-8 complete analysis, the eight-page report, and presentation. Deliverables include method-by-metric tables, adaptation differences, failure sequences, and reproducible manifests.

## References

Yangming Cheng, Liulei Li, Yuanyou Xu, Xiaodi Li, Zongxin Yang, Wenguan Wang, and Yi Yang. 2023. [Segment and track anything](https://arxiv.org/abs/2305.06558). arXiv:2305.06558.

Jonathon Luiten, Aljosa Osep, Patrick Dendorfer, Philip Torr, Andreas Geiger, Laura Leal-Taixe, and Bastian Leibe. 2020. [HOTA: A higher order metric for evaluating multi-object tracking](https://arxiv.org/abs/2009.07736). International Journal of Computer Vision.

Meta AI. 2026. [SAM 2 and SAM 2.1 training documentation](https://github.com/facebookresearch/sam2/blob/main/training/README.md). Online documentation, accessed October 7, 2026.

OpenCV. 2026. [Background subtraction](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html). Online documentation, accessed October 7, 2026.

Ultralytics. 2026. [Instance segmentation and multi-object tracking documentation](https://docs.ultralytics.com/modes/track/). Online documentation, accessed October 7, 2026.

Paul Voigtlaender, Michael Krause, Aljosa Osep, Jonathon Luiten, Berin Balachandar Gnana Sekar, Andreas Geiger, and Bastian Leibe. 2019. [MOTS: Multi-object tracking and segmentation](https://arxiv.org/abs/1902.03604). In CVPR.

Linjie Yang, Yuchen Fan, Yang Fu, and Ning Xu. 2021. [The 3rd Large-scale Video Object Segmentation Challenge - video instance segmentation track](https://youtube-vos.org/dataset/vis/).

Zongxin Yang and Yi Yang. 2022. [Decoupling features in hierarchical propagation for video object segmentation](https://github.com/yoxu515/aot-benchmark). In NeurIPS.
