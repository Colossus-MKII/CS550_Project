# 4. Evaluation metrics: what a good result means

[Guide index](README.md) · [Previous: SAM-Track and DeAOT](03-sam-track-and-deaot.md) · [Next: Proposal review](05-proposal-review.md)

A video can look convincing while missing difficult objects or swapping identities. We need measurements of discovery, pixel accuracy, identity consistency, and computational cost. The examples below are invented to explain the metrics; they are not project results.

## The common prediction format

Each method should ultimately describe the same kind of result:

```text
video ID + frame index + track ID + category + predicted mask
```

The exact serialization will be chosen during implementation. Masks must use the same image coordinates as the annotations. Define how absence is represented, how duplicate predictions are handled, and how categories are mapped. A track kept in memory during occlusion does not necessarily have a visible mask on that frame.

Ground truth supplies the reference masks and identities. Predicted IDs need not numerically equal ground-truth IDs; the evaluator establishes correspondences. Annotations are used for scoring, not as automatic-method prompts on evaluation videos.

## Mask IoU: are the selected pixels correct?

Intersection over union compares a predicted mask P with a reference mask G:

```text
IoU = number of pixels in both P and G
      / number of pixels in either P or G
```

If their intersection contains 80 pixels and their union contains 100, IoU is 0.80. Perfect overlap is 1; no overlap is 0. Box IoU instead compares rectangles, so a good box score does not establish a good mask score.

**Matched-mask mean IoU** is a useful diagnostic, not a complete accuracy measure. Suppose a system finds only one of ten dogs, with a perfect mask. Its mean IoU over that single matched object can be 1.0 while nine dogs are missed. Always read this measure alongside detection and tracking metrics. Specify which matching rule and threshold define “matched”; do not choose pairs separately to maximize the displayed mean. The October 13 proposal uses mask HOTA/DetA/AssA and IDF1 for tracking, with standalone box/mask AP50:95 to diagnose YOLO adaptation.

## HOTA: detection and association together

Higher Order Tracking Accuracy balances detecting the right objects with associating them correctly through time. At a particular overlap threshold alpha, its central relationship is:

```text
HOTA(alpha) = sqrt(DetA(alpha) * AssA(alpha))
```

DetA penalizes missed and extra detections. AssA measures temporal association quality, including identity fragmentation and incorrect identity merges. Localization matters through the overlap requirements used for matching. See the [HOTA paper](https://arxiv.org/abs/2009.07736).

TrackEval computes HOTA over thresholds 0.05, 0.10, ..., 0.95. The headline score averages the threshold-specific HOTA values; it is not generally the square root of separately averaged DetA and AssA. See the [HOTA implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/hota.py).

In our proposal, similarities are **mask IoUs**. “Mask-based HOTA” specifies the matching geometry; we are not inventing a new metric. For intuition, if DetA is 0.80 and AssA is 0.50 at one threshold, HOTA there is approximately 0.632. Finding most objects is not enough if identities are unreliable.

## IDF1: do identities remain consistent?

IDF1 uses a global correspondence between predicted and reference identities and combines identity precision and recall:

```text
IDF1 = 2 * IDTP / (2 * IDTP + IDFP + IDFN)
```

Here IDTP, IDFP, and IDFN are identity-based true positives, false positives, and false negatives. They are not necessarily the same counts as ordinary per-frame detection TP, FP, and FN. Our protocol uses mask IoU 0.5 for eligible matches. See the [TrackEval identity metric](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/identity.py).

Example: one object is visible for ten frames, with perfect masks. A system labels it track 7 for five frames and track 8 for five. Under this simple example's one-to-one identity assignment, only one predicted identity can match the true trajectory: IDTP=5, IDFP=5, IDFN=5, so IDF1=0.5. Pixel accuracy alone would miss the fragmentation.

## FP, FN, and identity switches

An FP is an unmatched predicted object; an FN is an unmatched annotated object. An identity switch records a change in an object's assigned predicted identity under the evaluator's temporal rules. The exact continuity and matching rules matter, so we should use a tested implementation rather than invent a counter. See [TrackEval's CLEAR metric implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/clear.py).

The October 13 proposal specifies TrackEval CLEAR diagnostic counts at mask IoU 0.5, alongside IDF1 at mask IoU 0.5. HOTA, IDF1, and CLEAR counts have their own matching procedures; a shared input adapter does not make their internal assignments identical.

## FPS and memory: how expensive is the whole system?

For our protocol, end-to-end FPS means evaluated frames divided by timed elapsed seconds. Include decoding, preprocessing, YOLO, prompt creation, propagation/association, and postprocessing. Exclude model loading, visualization, and scoring as specified in the proposal, and record those exclusions. Preloading or caching must not silently remove work from only one method's timing.

Peak GPU memory needs a named measurement method. Framework-allocated memory, framework-reserved memory, and process memory reported by the driver are not interchangeable. Record GPU model, precision, frame dimensions, object count, video length, and any CPU offloading. Synchronize GPU work around timing, warm up, and report the median of three runs under the same conditions.

More FPS is better for throughput; less memory is better for capacity. Neither establishes greater accuracy. Keeping the full quality-versus-cost table is more informative than naming one universal winner.

## Dataset scores and evaluator checks

The official YouTube-VIS benchmark uses video-instance average precision, which differs from this internal HOTA/IDF1 study. Do not compare our numbers directly to its leaderboard. See the [official evaluation description](https://youtube-vos.org/dataset/vis/).

TrackEval already provides a YouTube-VIS loader that computes mask similarities. Start by checking whether it can support our subset and export format; “adapter” need not mean rewriting the metrics. See the [dataset implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/datasets/youtube_vis.py).

Before scoring models, test perfect predictions, consistent ID renaming, missed masks, an extra object, an identity switch, a wrong category, and absent-object frames. Perfect scores and invariance to consistent renaming are useful sanity checks. Other cases should worsen the relevant metrics, not necessarily every metric.

Report each target category and the proposal's unweighted category mean. A category with no evaluable ground truth needs an explicit policy, not an unexplained zero. Also preserve per-video diagnostics. Averaging per-video scores is not automatically equivalent to combining a metric's statistics across videos; label the aggregation used.
