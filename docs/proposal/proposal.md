# Comparing Methods for Multi Object Segmentation and Tracking

**Jingdi Wu, Yupu Guo, Christina Ross**  
Rutgers University · CS550 Massive Data Mining · Fall 2026  
Project proposal · October 7 2026

## Abstract

This project will compare four approaches to segmenting objects and keeping their identities consistent in video: YOLO segmentation with ByteTrack or BoT-SORT, SAM 2.1, SAM-Track, and OpenCV background subtraction. We will study people, animals, and vehicles, measuring mask quality, missed objects, identity errors, and processing cost. We will also compare pretrained models with fine-tuned versions where computing resources allow. The aim is to understand which errors each approach makes and whether adaptation helps on videos it has not seen during training.

## 1 Introduction

When two similar objects cross paths, a tracker may swap their identities even if their outlines remain accurate. Occlusion, changes in lighting, and camera movement can make this problem harder. We will examine how segmentation quality relates to tracking accuracy and whether fine-tuning improves both. The project covers several object categories rather than only vehicles. Our focus is maintaining object tracks; estimating whether an object is physically moving relative to the world is outside the study.

## 2 Methods

YOLO11s-seg will be paired separately with ByteTrack and BoT-SORT, allowing us to compare two trackers using the same segmenter (Ultralytics, 2026). SAM 2.1 will propagate prompted masks through its video memory (Meta AI, 2026). SAM-Track will use SAM on keyframes and DeAOT between them, with periodic checks for new objects (Cheng et al., 2023). For the classical baseline, we will test OpenCV's MOG2 and KNN background subtraction methods (OpenCV, 2026), separate their foreground regions into instances, and associate these instances across frames using mask IoU.

SAM 2.1 and SAM-Track will receive box prompts and category labels from the same frozen YOLO detector. It will also help label and separate OpenCV's foreground regions. The interval for adding new objects will be chosen on validation videos. The detector will not supply tracking IDs, and its processing time will count toward each pipeline's runtime. Automatic runs will use no ground-truth prompts from evaluation videos. If we also test propagation from ground-truth masks, those results will be reported separately.

We will fine-tune YOLO's segmenter and test the resulting weights with both trackers. We also plan to fine-tune SAM 2.1 and SAM-Track's DeAOT component, keeping SAM fixed in the latter case (Yang and Yang, 2022). These two experiments depend on successful GPU and training-data pilots. To isolate weight adaptation, each comparison will keep prompts, the shared detector, tracking settings, and image preparation unchanged. OpenCV's history, thresholds, and learning rate will be tuned on validation videos. Its online background updates and tracker settings are parameter adaptation, not neural fine-tuning.

## 3 Dataset and Experiments

We will select up to 200 labeled videos from the YouTube-VIS 2021 training set, covering people, dogs, cats, horses, and cars (Yang et al., 2021). Whole videos will be divided into training, validation, and evaluation sets in a 60/20/20 ratio, with category coverage in each set. Frames from one video will stay in one split. YOLO will train on sampled images with instance masks; SAM 2.1 and DeAOT need annotated video clips.

Every method will process the same frames in the same order. We will report results separately for fixed and moving cameras, since background subtraction is sensitive to camera movement. We will also test blur, brightness changes, and JPEG compression on the same evaluation clips. These changes preserve the mask coordinates. Model selection and parameter tuning will use only training and validation data. We will record annotation coverage, any known overlap with model pretraining, and the splits, checkpoints, and settings used in each experiment.

## 4 Evaluation

Our main measures will be sMOTSA and mask-based HOTA, including DetA and AssA (Voigtlaender et al., 2019; Luiten et al., 2020). sMOTSA combines matched-mask overlap with penalties for false positives and identity switches. HOTA helps distinguish missed detections from poor identity association. We will also report MOTSA, MOTSP, mask-matched IDF1, ID switches, and false positives and negatives. MOTSP scores matched masks only, so it must be read alongside missed-object counts.

MOTS matching requires non-overlapping masks and mask IoU above 0.5; HOTA uses its standard threshold sweep. We will check category mapping, frame indices, absent objects, ignore regions, and overlap resolution before computing scores. The five-category conversion needs validation rather than an unchanged car/pedestrian-only loader. We will describe these as MOTS-style results on our YouTube-VIS subset, with native video AP as an additional measure.

For robustness, we will measure changes from each clean clip to its corrupted versions and inspect identity failures around occlusion. Speed, peak GPU memory, and training time will show the cost of each method. Timing will include detection, prompting, object discovery, and postprocessing. We will estimate uncertainty by resampling videos where practical. Mask overlap between adjacent frames alone cannot measure stability, because the objects themselves move.

## 5 Work Plan

Our lab GPU allocation is still unconfirmed. We will first test 100 inference frames and 20 training steps for each neural candidate to check memory, gradients, checkpoint loading, and expected training time. We will start with smaller checkpoints and record which components are trainable. If training does not fit, we will report pretrained results where inference is feasible and explain the missing experiment.

During weeks 1-2 we will prepare the data and baseline pipelines. Weeks 3-4 will cover parameter tuning and feasible fine-tuning, followed by evaluation and robustness experiments in weeks 5-6. In weeks 7-8 we will analyze the failures and complete the eight-page report, excluding references, and the presentation.

## References

Yangming Cheng, Liulei Li, Yuanyou Xu, Xiaodi Li, Zongxin Yang, Wenguan Wang, and Yi Yang. 2023. [Segment and track anything](https://arxiv.org/abs/2305.06558). arXiv:2305.06558.

Jonathon Luiten, Aljosa Osep, Patrick Dendorfer, Philip Torr, Andreas Geiger, Laura Leal-Taixe, and Bastian Leibe. 2020. [HOTA: A higher order metric for evaluating multi-object tracking](https://arxiv.org/abs/2009.07736). International Journal of Computer Vision.

Meta AI. 2026. [SAM 2 and SAM 2.1 training documentation](https://github.com/facebookresearch/sam2/blob/main/training/README.md). Online documentation, accessed October 7, 2026.

OpenCV. 2026. [Background subtraction](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html). Online documentation, accessed October 7, 2026.

Ultralytics. 2026. [Instance segmentation and multi-object tracking documentation](https://docs.ultralytics.com/modes/track/). Online documentation, accessed October 7, 2026.

Paul Voigtlaender, Michael Krause, Aljosa Osep, Jonathon Luiten, Berin Balachandar Gnana Sekar, Andreas Geiger, and Bastian Leibe. 2019. [MOTS: Multi-object tracking and segmentation](https://arxiv.org/abs/1902.03604). In CVPR.

Linjie Yang, Yuchen Fan, Yang Fu, and Ning Xu. 2021. [The 3rd Large-scale Video Object Segmentation Challenge - video instance segmentation track](https://youtube-vos.org/dataset/vis/).

Zongxin Yang and Yi Yang. 2022. [Decoupling features in hierarchical propagation for video object segmentation](https://github.com/yoxu515/aot-benchmark). In NeurIPS.
