# Comparing Methods for Multi Object Segmentation and Tracking

**Jingdi Wu, Yupu Guo, Christina Ross**  
Rutgers University · CS550 Massive Data Mining · Fall 2026  
Project proposal · October 7 2026

## Abstract

This project will compare YOLO segmentation with ByteTrack or BoT-SORT, SAM 2.1, SAM-Track, and OpenCV background subtraction on people, animals, and vehicles. We will measure mask quality, missed objects, identity errors, and processing cost, and present synchronized tracking videos. Where computing resources allow, we will compare pretrained and fine-tuned versions to examine whether adaptation improves performance on videos held out from our fine-tuning.

## 1 Introduction

When similar objects cross paths, a tracker may swap their identities even if their outlines remain accurate. Occlusion, lighting changes, and camera movement can make this harder. We will examine how mask quality relates to tracking accuracy and whether fine-tuning improves both across several categories. We study persistent object tracks, rather than estimating whether an object is physically moving relative to the world.

## 2 Methods

YOLO11s-seg will be paired separately with ByteTrack and BoT-SORT to compare two trackers using one segmenter (Ultralytics, 2026). SAM 2.1 will propagate prompted masks through video memory (Meta AI, 2026). SAM-Track will use SAM on keyframes and DeAOT between them, with periodic object discovery (Cheng et al., 2023). OpenCV's MOG2 and KNN will provide classical baselines (OpenCV, 2026), with foreground regions separated into instances and associated across frames by mask IoU.

SAM 2.1 and SAM-Track will receive box prompts and categories from a shared frozen YOLO detector, also used to label and separate OpenCV's foreground regions. The object-discovery interval will be chosen on validation videos. The detector will supply no tracking IDs, and its time will count toward runtime. Automatic runs will use no evaluation ground-truth prompts; any ground-truth-initialized propagation will be reported separately.

We plan to fine-tune YOLO's segmenter for both trackers. SAM 2.1 and DeAOT fine-tuning depend on successful GPU and training-data pilots; SAM will remain fixed when adapting DeAOT (Yang and Yang, 2022). Each pretrained/adapted pair will use identical prompts, shared detector, tracking settings, and image preparation. OpenCV's history, thresholds, and learning rate will be tuned on validation videos. These settings and online background updates constitute parameter adaptation, not neural fine-tuning.

## 3 Dataset and Experiments

We choose YouTube-VIS 2021 for its category labels, instance masks, and identities across frames (Yang et al., 2021). It includes animals, unlike car/pedestrian-focused KITTI MOTS and pedestrian-only MOTSChallenge (Voigtlaender et al., 2019). We fix the release for reproducibility, without claiming superiority over 2022's longer validation/test extension. Our short-clip subset will not establish long-term tracking performance.

We will select up to 200 labeled training videos covering people, dogs, cats, horses, and cars. Whole videos will be split 60/20/20 for training, validation, and evaluation, preserving category coverage and preventing frame leakage. YOLO will train on images with instance masks; SAM 2.1 and DeAOT need annotated clips. We will check source-video overlap with upstream pretraining, especially YouTube-VOS-derived data. Our held-out split alone cannot establish that pretrained models have never seen a video.

Every method will process identical frame sequences. We will separate fixed- and moving-camera results and test blur, brightness changes, and JPEG compression without changing mask coordinates. Model selection and tuning will use training/validation data only. We will record annotation coverage, pretraining overlap, splits, checkpoints, and settings.

## 4 Evaluation

The original MOTS measures are Multi-Object Tracking and Segmentation Accuracy (MOTSA), soft Multi-Object Tracking and Segmentation Accuracy (sMOTSA), and Multi-Object Tracking and Segmentation Precision (MOTSP) (Voigtlaender et al., 2019). MOTSA counts matches and penalizes false positives and identity switches; sMOTSA weights matches by mask intersection over union (IoU). Both normalize by total ground-truth masks across frames. MOTSP averages matched-mask IoU, excluding missed objects.

Supplementary measures are mask-based Higher Order Tracking Accuracy (HOTA), Detection Accuracy (DetA), Association Accuracy (AssA), and Localization Accuracy (LocA) (Luiten et al., 2020). HOTA balances detection and association; LocA describes matched-mask overlap. We will report mask-matched identity F1 score (IDF1), identity switches (IDS), false positives (FP), and false negatives (FN). Higher scores and lower error counts are better. sMOTSA and HOTA are our primary measures.

MOTS matching requires non-overlapping masks and mask IoU above 0.5; HOTA uses its standard threshold sweep. We will validate category mapping, frame indices, absent objects, ignore regions, and overlap resolution. The five-category conversion needs more than an unchanged car/pedestrian loader. These will be internal MOTS-style results on our YouTube-VIS subset, with native video AP as an additional measure.

We will show synchronized videos and report figures with identical frames, mask contours, persistent predicted IDs, and ground-truth references. Panels cover both YOLO trackers, SAM 2.1, SAM-Track, MOG2, and KNN, plus adapted versions where available. Colors remain tied to each pipeline's IDs. Fixed held-out clips will illustrate fixed/moving cameras, occlusion, crossings, and entry/re-entry. Successes and failures will be linked to identity switches, missed objects, mask errors, and per-clip scores.

Robustness scores will compare clean clips with their corrupted versions. We will report FPS, peak GPU memory, and training time; timing includes detection, prompting, discovery, and postprocessing. Where practical, uncertainty will be estimated by resampling videos. Adjacent-frame mask overlap alone cannot measure stability because objects move.

## 5 Computing Resources

GPU allocation is unconfirmed. We will ask the instructor about GPU models, memory, access limits, and training budget before committing to SAM 2.1 or DeAOT fine-tuning. An inference/training pilot with smaller checkpoints will check memory, gradients, checkpoint loading, and training cost. We will record trainable components and report pretrained results where training is impractical but inference is feasible.

## References

Yangming Cheng, Liulei Li, Yuanyou Xu, Xiaodi Li, Zongxin Yang, Wenguan Wang, and Yi Yang. 2023. [Segment and track anything](https://arxiv.org/abs/2305.06558). arXiv:2305.06558.

Jonathon Luiten, Aljosa Osep, Patrick Dendorfer, Philip Torr, Andreas Geiger, Laura Leal-Taixe, and Bastian Leibe. 2020. [HOTA: A higher order metric for evaluating multi-object tracking](https://arxiv.org/abs/2009.07736). International Journal of Computer Vision.

Meta AI. 2026. [SAM 2 and SAM 2.1 training documentation](https://github.com/facebookresearch/sam2/blob/main/training/README.md). Online documentation, accessed October 7, 2026.

OpenCV. 2026. [Background subtraction](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html). Online documentation, accessed October 7, 2026.

Ultralytics. 2026. [Instance segmentation and multi-object tracking documentation](https://docs.ultralytics.com/modes/track/). Online documentation, accessed October 7, 2026.

Paul Voigtlaender, Michael Krause, Aljosa Osep, Jonathon Luiten, Berin Balachandar Gnana Sekar, Andreas Geiger, and Bastian Leibe. 2019. [MOTS: Multi-object tracking and segmentation](https://arxiv.org/abs/1902.03604). In CVPR.

Linjie Yang, Yuchen Fan, Yang Fu, and Ning Xu. 2021. [The 3rd Large-scale Video Object Segmentation Challenge - video instance segmentation track](https://youtube-vos.org/dataset/vis/).

Zongxin Yang and Yi Yang. 2022. [Decoupling features in hierarchical propagation for video object segmentation](https://github.com/yoxu515/aot-benchmark). In NeurIPS.
