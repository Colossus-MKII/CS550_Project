# 3. SAM-Track and DeAOT

[Guide index](README.md) · [Previous: SAM 2.1](02-sam2.md) · [Next: Evaluation metrics](04-evaluation-metrics.md)

Scope note, October 13: SAM-Track/DeAOT is retained as background reading. The current proposal prioritizes YOLO adaptation in two pipelines and does not include this third pipeline or DeAOT training.

## The one-sentence explanation

SAM-Track combines an image-segmentation model with a separate video-propagation model; DeAOT is the propagation component, not another name for SAM or SAM 2.

## Three names that should not be conflated

**Original SAM** produces image masks from spatial prompts. Its automatic mask generator can propose many regions without manual clicks, but that does not provide our five semantic category labels or persistent identities over time. See the [original SAM repository](https://github.com/facebookresearch/segment-anything).

**DeAOT** performs video object segmentation using reference masks that identify the target objects. In this context, “semi-supervised video object segmentation” usually describes an inference task with supplied reference annotations, commonly on the first frame. It does not mean we must fine-tune the network on every new video. See the [DeAOT paper](https://arxiv.org/abs/2210.09782).

**SAM-Track**, also called Segment and Track Anything, connects segmentation and temporal propagation. Its original design uses SAM for key-frame segmentation and DeAOT for following the resulting objects. It supports automatic and interactive workflows; text-conditioned examples involve additional grounding functionality. This is a framework, not one checkpoint. See the [SAM-Track paper](https://arxiv.org/abs/2305.06558).

## What DeAOT learns to do

DeAOT builds on Associating Objects with Transformers (AOT). Its central idea is to maintain separate propagation branches for general visual information and object-specific identity information. Informally, the network needs both “what this region looks like” and “which initialized object this region belongs to.” Keeping these representations separate is intended to preserve useful visual information while propagating identities. See the [DeAOT method description](https://arxiv.org/abs/2210.09782).

For example, a reference mask can specify that the left dog is object 1 and the right dog is object 2. DeAOT then predicts their masks on subsequent frames. Supplying those reference masks is a separate problem from propagating them. A new dog is not automatically assigned a project-level track identity merely because a propagation model is running.

## Original workflow versus the earlier optional experiment

The upstream framework periodically invokes SAM to discover additional regions, with a configurable `sam_gap`. It can also use GroundingDINO in text-guided workflows. Its discovery behavior is therefore not necessarily the same as the detector-assisted policy in our proposal. See the [official SAM-Track README](https://github.com/z-x-yang/Segment-and-Track-Anything).

The earlier proposal considered this optional adaptation:

```text
YOLO boxes and categories
  -> matching and object-management rules
  -> original SAM converts selected boxes into image masks
  -> DeAOT receives identity-labeled reference masks
  -> DeAOT propagates those objects through subsequent frames
```

This is an unimplemented background design, not part of the current experiment plan. It would require checking interfaces for adding objects, refreshing references, preserving identities, and resolving overlapping masks. Replacing the upstream discovery mechanism with YOLO changes the system; such a study should call it a detector-assisted SAM-Track/DeAOT adaptation rather than an exact reproduction of published results.

The intended comparison with pipeline B is then two different ways of turning detector prompts into temporally consistent masks. However, their internal memory, refresh behavior, and object management still differ. A shared detector does not remove every confounding factor.

## What our downloaded checkpoint means

`DeAOTB_PRE_YTB_DAV.pth` corresponds to the DeAOT-B variant. In the official model zoo, `PRE` denotes static-image pretraining and `PRE_YTB_DAV` denotes subsequent training with YouTube-VOS and DAVIS. This filename records upstream training history; it is not an instruction for us to train those stages. See the [official model zoo](https://github.com/yoxu515/aot-benchmark/blob/main/MODEL_ZOO.md).

YouTube-VOS and YouTube-VIS are different benchmarks with related source material: the [YouTube-VIS dataset page](https://youtube-vos.org/dataset/vis/) describes its relationship to YouTube-VOS. Consequently, possible overlap between pretrained data and our selected clips must be investigated. The filename alone neither proves nor rules out overlap with a particular evaluation video.

The local checkpoint inventory does not contain an original SAM checkpoint. The upstream setup requires both SAM and DeAOT weights, plus matching code/configurations and dependencies. Downloading DeAOT alone therefore does not complete this pipeline. See [upstream model preparation](https://github.com/z-x-yang/Segment-and-Track-Anything).

## Why it is outside the current scope

Adding this method introduces another integration, environment, and evaluation path. The October 13 revision instead allocates that effort to testing whether one adapted YOLO improves both existing pipelines. Background explanations and downloaded resources are retained, but do not constitute a commitment to run this method.

Expected failure cases to investigate include a poor reference mask, drift toward a similar nearby object, accumulated propagation errors, and duplicate initialization when discovery fails to recognize an existing track. These are proposed checks, not measured failures in our repository.

## Other names from the earlier proposal

**BoT-SORT** is another tracking-by-detection method, not a segmentation model. The Ultralytics implementation offers camera-motion compensation and optional appearance-based re-identification. Those features could change both identity performance and runtime, so substituting it for ByteTrack would be a different experiment. It is outside the revised core scope. See the [tracking documentation](https://docs.ultralytics.com/modes/track/).

**MOG2 and KNN background subtraction** estimate foreground relative to a background model. Their output does not by itself provide semantic object categories or persistent individual IDs. A foreground region can also contain several touching objects. They are useful for understanding the distinction between motion-oriented foreground extraction and our current object-level task, but are not required baselines. See the [OpenCV background-subtraction tutorial](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html).
