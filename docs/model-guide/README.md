# Model study guide for the CS550 project

English learning notes for the [revised proposal](../proposal/proposal.md). Prepared October 10; scope updated October 13, 2026.

The central idea is to compare two complete systems: one finds objects again in each frame and links the detections; the other finds objects periodically and propagates their masks through time. We are not training a new foundation model.

The October 13 revision first evaluates pretrained A0/B0, then prioritizes one small YOLO fine-tune whose selected checkpoint is reused in A1/B1. SAM 2.1 remains frozen. The two pretrained baselines are the minimum deliverable; training is feasibility-gated, and a positive gain is not required. SAM-Track/DeAOT is background reading, not a third planned experiment.

This guide separates established model capabilities from our proposed integration choices. Examples are illustrative, not measured results. Downloaded checkpoints do not mean the pipelines have been implemented or tested.

## Reading order

| Read | Main question |
| --- | --- |
| [1. YOLO11s-seg and ByteTrack](01-yolo-and-bytetrack.md) | How do detection, segmentation, and identity association fit together? |
| [2. SAM 2.1](02-sam2.md) | What does prompted video segmentation do, and what must we add? |
| [3. SAM-Track and DeAOT](03-sam-track-and-deaot.md) | How does this background approach differ from SAM 2? |
| [4. Evaluation metrics](04-evaluation-metrics.md) | What do IoU, HOTA, IDF1, FPS, and memory actually measure? |
| [5. Reviewing our proposal](05-proposal-review.md) | Which assumptions and implementation decisions need checking? |

For a quick review, read this page, Chapters 1 and 2, and the decision table in Chapter 5. Chapter 3 is optional for the required two-method study.

## First distinguish the tasks

Imagine two dogs crossing in a video:

| Task | Question | Example output |
| --- | --- | --- |
| Classification | What kind of object is this? | `dog` |
| Object detection | Where is each object? | Two bounding boxes labeled `dog` |
| Instance segmentation | Which pixels belong to each individual object? | A separate mask for each dog |
| Tracking | Which individual is the same one over time? | Dog A stays track 7; dog B stays track 12 |
| Motion detection | Which image regions changed relative to a background or earlier frame? | Foreground regions, not necessarily recognized objects |

A **mask** is a pixel-level selection. A **bounding box** is a rectangle and includes background around an irregular object. A **class label** such as `dog` is shared by many objects; a **track ID** distinguishes individuals within one video. The number itself has no meaning: consistently calling dog A “7” or “42” is equally valid.

A stationary dog still belongs in our current project. Conversely, a moving shadow is not a target animal or vehicle. The proposal studies object segmentation and identity continuity, not a test of whether an object is physically moving.

## Which component does which job?

| Component | Main input | Main output or role | Project status |
| --- | --- | --- | --- |
| YOLO11s-seg | One image/frame | Category, confidence, box, and instance mask | Required in both pipelines |
| ByteTrack | Frame-by-frame detection boxes and scores | Association of detections with track IDs | Required in pipeline A |
| SAM 2.1 Hiera Tiny | Frames plus spatial prompts and object state | Masks propagated for specified objects | Required in pipeline B |
| Original SAM | Image plus spatial prompts, or automatic mask-generation procedure | Image masks | Background: part of SAM-Track |
| DeAOT | Frames plus reference masks carrying object identities | Subsequent masks for those objects | Background; outside current scope |
| SAM-Track | Video and an initialization/discovery mechanism | A combined segmentation-and-tracking workflow | Background; outside current scope |

The technical sources and qualifications for these roles appear in the corresponding chapters. Not every row is a “large model”: ByteTrack is an association algorithm, and SAM-Track is a framework containing multiple components. None of these is a large language model.

## Our proposed systems at a glance

```text
A: every evaluated frame
   -> YOLO11s-seg boxes, categories, masks
   -> ByteTrack associates boxes
   -> matched YOLO masks with track IDs

B: selected discovery/refresh frames
   -> shared YOLO11s-seg supplies boxes and categories (pretrained B0 / adapted B1)
   -> our matching and track-management code assigns prompt IDs
   -> SAM 2.1 propagates masks across the evaluated frames
   -> SAM masks with track IDs and externally maintained categories

C, earlier idea retained for background only:
   YOLO discovery -> SAM image masks -> DeAOT propagation
   with explicit matching, new-object, and retirement policies
```

In B, “category” is metadata in our code, not a text instruction to SAM 2.1. In C, using YOLO discovery is our proposed adaptation, not a claim to reproduce every setting of the original SAM-Track paper.

## Files already downloaded

These sizes describe local files, not GPU memory requirements.

| File under `models/checkpoints/` | Approximate disk size, decimal MB | Intended use |
| --- | ---: | --- |
| `yolo11s-seg.pt` | 20.7 | Core detector/segmenter |
| `sam2.1_hiera_tiny.pt` | 156.0 | Core SAM 2.1 model |
| `sam2.1_hiera_small.pt` | 184.4 | Extra variant; not a required experiment |
| `DeAOTB_PRE_YTB_DAV.pth` | 158.5 | Background propagation model; outside current scope |

The local inventory and recorded hashes are in [downloaded-resources.json](../../resources/downloaded-resources.json). An original SAM checkpoint is not present in this inventory, so the background SAM-Track setup is incomplete. The inventory lists local downloads; it does not include the weights or videos in Git.

“Pretrained” means weights were learned upstream. “Frozen inference” means using those weights without changing them. “Fine-tuning” updates weights using our training data. Choosing thresholds on validation data is tuning the experiment, but is not neural-network fine-tuning. Updating a track's position or a model's video memory is also not weight training.

Next: [YOLO11s-seg and ByteTrack](01-yolo-and-bytetrack.md).
