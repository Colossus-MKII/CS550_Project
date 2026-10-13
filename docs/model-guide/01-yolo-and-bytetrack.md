# 1. YOLO11s-seg and ByteTrack

[Guide index](README.md) · [Next: SAM 2.1](02-sam2.md)

## The one-sentence explanation

YOLO11s-seg finds and outlines objects in an image; ByteTrack connects detections across frames so that an individual can keep its ID.

## What YOLO11s-seg does

In the checkpoint name, `11` identifies the YOLO generation, `s` the small model variant, and `-seg` the instance-segmentation task. `yolo11s.pt` and `yolo11s-seg.pt` are not interchangeable: the detection-only checkpoint does not provide instance masks. The official pretrained segmentation models use COCO's category vocabulary. Our five target names are person, dog, cat, horse, and car; their dataset-specific numeric IDs must still be mapped explicitly. See the [YOLO11 documentation](https://docs.ultralytics.com/models/yolo11/).

Given one frame, a segmentation prediction contains boxes, class predictions, confidence scores, and object masks. It does not by itself establish that a dog in this frame is the same dog in the next one. Confidence is a model score used for filtering; it is not a promise that a mask has that percentage of pixels correct. See the [instance-segmentation task documentation](https://docs.ultralytics.com/tasks/segment/).

At a high level, the network extracts image features, combines information at different spatial scales, and uses prediction heads to produce detections and masks. The segmentation configuration connects multi-scale features to a `Segment` head. You do not need to understand every layer to review the proposal; the important distinction is per-image prediction versus temporal association. See the [versioned YOLO11 segmentation configuration](https://github.com/ultralytics/ultralytics/blob/v8.3.0/ultralytics/cfg/models/11/yolo11-seg.yaml).

### A concrete example

Suppose one frame produces these illustrative predictions:

```text
Detection 0: class=dog, confidence=0.93, box=[40, 80, 180, 230], mask=A
Detection 1: class=dog, confidence=0.88, box=[220, 90, 350, 240], mask=B
```

The box format here is `[left, top, right, bottom]` in image coordinates. A and B are full pixel masks, not their bounding boxes. “Detection 0” is only an index in this frame's result. It cannot serve as a persistent identity: prediction ordering can change in the next frame.

## What ByteTrack adds

ByteTrack's central idea is to use lower-confidence detections to recover existing tracks, rather than discarding all of them immediately. A partially hidden person may yield a weak detection that still matches their recent trajectory. This is not an instruction to accept every weak box as a new object. See the [ByteTrack paper](https://arxiv.org/abs/2110.06864).

The basic sequence is:

1. Predict approximate current positions of existing tracks using a motion model.
2. Associate stronger detections with eligible tracks.
3. Try remaining eligible tracks against weaker detections.
4. Start tracks from suitable unmatched strong detections; retain lost tracks temporarily and eventually retire them.

The inspected Ultralytics implementation uses a Kalman filter and box-overlap-based assignment, optionally combined with detection scores. It stores tracked, lost, and removed states. Basic ByteTrack does not require a separate neural appearance-recognition checkpoint. The [versioned implementation](https://github.com/ultralytics/ultralytics/blob/v8.3.0/ultralytics/trackers/byte_tracker.py) is a concrete reference, not a claim that this package version is installed or has been selected for our experiments.

For the two-dog example, the tracker might associate the current left-hand detection with track 7 and the right-hand detection with track 12. If the dogs cross, successful tracking follows each dog, not whichever dog occupies the left side.

## Where the masks come from

In pipeline A, masks come from YOLO, not from ByteTrack. The implementation must attach each accepted track ID to the correct current-frame YOLO mask. A predicted box for a temporarily lost track is not a newly observed segmentation mask.

This distinction creates an important check: never assume that the first tracker output corresponds to the first original detector output. Filtering and association can reorder or discard detections. Preserve the mapping explicitly and visually inspect it on a two-object sequence.

Ultralytics supports tracking with segmentation models and selecting a tracker configuration. Specify `tracker="bytetrack.yaml"` explicitly; do not depend on whichever tracker a package version chooses by default. Maintain state within a video and reset it between videos. See the [tracking documentation](https://docs.ultralytics.com/modes/track/).

## Settings that can change the conclusion

These are project implementation concerns, not additional neural models:

| Decision | Why it matters |
| --- | --- |
| Detector confidence cutoff | If weak detections are removed before ByteTrack sees them, its recovery stage cannot use them. |
| Detector duplicate suppression | Removing or retaining overlapping candidates affects both misses and duplicate tracks. |
| Track initialization threshold | Too permissive can create false tracks; too strict can delay discovery. |
| Lost-track buffer | Determines how long an identity can survive a temporary detection failure. |
| Class policy | Tracking two different categories together can behave differently from explicitly class-gated association. |
| Frame sampling | A five-frame gap can contain much more motion than a one-frame gap. |

Do not confuse detector duplicate-suppression IoU, tracker matching thresholds, and evaluation mask IoU. They operate at different stages and need not use the same values.

In particular, the inspected v8.3.0 `get_dists` function does not explicitly gate matches by category. Class-aware *evaluation* does not make *tracking* class-aware. Check the selected implementation before claiming otherwise. If we introduce per-class trackers or category gating, document the adaptation and keep IDs unique within the video. This is a review finding, not a change already made to the baseline.

## Expected strengths and failure cases

Our working hypotheses are that pipeline A will offer straightforward automatic discovery and a relatively simple implementation, but may struggle when detections disappear or similar objects cross. Abrupt camera movement can also make a simple position-based association less reliable. These are reasons to select diagnostic clips, not results we have measured.

A good outline does not guarantee a correct identity. Likewise, correct identity can coexist with a poor mask. We therefore need both segmentation and association metrics.

## Training and project role

The A0/B0 baselines use pretrained YOLO weights unchanged. The prioritized adaptation study fine-tunes one YOLO checkpoint on labeled training frames, selects it on validation data, and reuses it in A1/B1; it must not replace the baseline results. ByteTrack's thresholds and motion state are not trained YOLO weights. The October 13 proposal chooses per-category ByteTrack instances with video-wide unique IDs; this planned class-gated variant still needs implementation and validation. Detector thresholds and downstream rules stay fixed within each before/after pair.

Before accepting pipeline A as complete, verify that it produces correctly aligned masks and IDs, handles an empty-detection frame, resets between videos, and exports every evaluated frame in the common format.
