# Multi-Object Segmentation and Tracking: Historical State and Error Recovery

**Jingdi Wu, Yupu Guo, Christina Ross**

Rutgers University · CS550 Massive Data Mining · Fall 2026
Three-page proposal body · October 15, 2026

## Abstract

We will compare YOLO11s-seg with ByteTrack and detector-assisted SAM 2.1, then investigate how historical state affects recovery in both pipelines. With model weights fixed, paired experiments will retain or reinitialize motion state and visual history after identical corrective information. Recovery curves and failure analysis will examine when history helps, impedes, or has little effect on recovery. If supported by evidence, one simple policy will be tested in its automatic pipeline.

## 1 Research questions

Detection, segmentation, and identity association have different failure sources. A returning object receiving a new ID does not alone justify detector training. Both ByteTrack and SAM use history, but their representations differ. We ask:

- **RQ1: System comparison.** How do the automatic pipelines differ in quality, cost, and main failure types?
- **RQ2: Conditional recovery.** When does retaining or resetting history help, considering prior prediction quality, new-observation quality, and scene changes?
- **RQ3: Recovery dynamics.** How long do effects persist, and can the observed patterns inform an automatic policy?

## 2 Related work

ByteTrack combines detection association with Kalman motion prediction (Zhang et al., 2021). OC-SORT addresses motion-state errors under occlusion and nonlinear movement (Cao et al., 2023). SAM 2 propagates prompted masks using visual memory (Ravi et al., 2024); SAM2Long explores candidate histories and memory selection (Ding et al., 2025), while SAMURAI adds motion consistency (Yang et al., 2024). These motivate controlled recovery analysis, rather than additional mandatory baselines. Our contribution is comparison, explanation, and system validation; we do not claim resetting itself as a new algorithm.

<!-- pagebreak -->

## 3 Baselines and controlled recovery

### Automatic baselines

**A0: YOLO11s-seg + ByteTrack.** Run pretrained YOLO every frame, associate detections with separate trackers per category, and attach video-wide unique IDs to the corresponding YOLO masks.

**B0: Detector-assisted SAM 2.1.** Use the same YOLO weights periodically. Match same-category detections to propagated-mask boxes by box IoU, refresh matched prompts while retaining SAM 2.1 Hiera Tiny history, and create IDs for accepted unmatched detections. B0 uses neither ByteTrack IDs nor annotation prompts. Neither baseline includes explicit long-term appearance re-identification.

### Paired recovery

Distinguish observation errors, association/lifecycle errors, and failures after correctly routed new information. Select stable tracking, occlusion, re-entry, abrupt-motion, and distractor events without inspecting which strategy wins. The four-group study requires operable target state in both systems; report deleted-track and other ineligible cases separately.

At one correction time, fork each pipeline's own pre-correction state. Both branches receive identical corrective information:

| Group | History treatment | Correction |
| --- | --- | --- |
| A-H | Retain motion state | Normal Kalman update with the corrective box |
| A-R | Reinitialize motion state | Same-box position/size, zero velocity, default initial covariance |
| B-H | Retain visual history | Add the same box prompt to the existing target |
| B-R | Reinitialize target inference state | Clear old prompts, visual memory, and associated state; initialize from the same box |

H receives correction too. Preserve external IDs, align post-correction alive/lifecycle handling within each pair, and do not actively reset other targets. The systems' reset operations are not internally equivalent. Branch states must remain independent after forking.

Separately study actual YOLO boxes and reference boxes derived from the current frame's annotations. Fix correction time, coordinates, source, and target routing within pairs; process the correction once. Reference boxes need not produce perfect masks. This diagnostic routing tests recovery after receiving a correction, not automatic re-identification.

After correction, preserve each pipeline's native input schedule: continued detections for ByteTrack and predefined automatic refreshes for SAM. No further annotation assistance is supplied. Predictions and associations may diverge. Retain uncorrected baseline trajectories as references and report automatic and controlled results separately.

### Interpretation and follow-up

Compare within-pipeline effects before cross-system patterns; detection frequency, representation, and association remain confounders. If evidence supports it, test at most one automatic policy against its unchanged baseline, using inference-time signals only. Otherwise, paired findings remain the research outcome. All core model weights remain fixed.

<!-- pagebreak -->

## 4 Data and controls

Select 200 annotated YouTube-VIS 2021 training videos covering person, dog, cat, horse, and car. With seed 550, split whole videos into 120 development, 40 validation, and 40 held-out evaluation videos; keep same-source clips together before frame sampling.

A small pilot checks interventions, event coverage, annotation density, and observation length. Freeze event rules, recovery thresholds, windows, and any policy before inspecting held-out results. Use identical ordered frames and external resizing, record preprocessing and versions, and map outputs to annotation coordinates. Process forward only. Pre-correction true overlap is an offline diagnostic proxy, not a policy input; natural-scene correlations alone do not establish causality. The full review details implementation controls.

## 5 Evaluation and outcomes

### Complete systems

Report class-aware mask HOTA, DetA, AssA (Luiten et al., 2020), IDF1 at mask IoU 0.5, false positives, misses, ID switches, and standalone YOLO box/mask AP50:95. Validate scoring with perfect predictions, misses, and ID switches. Combine videos within classes according to metric rules, then weight classes equally.

### Recovery dynamics

Fix the designated target correspondence/ID, exclude the corrected frame, and count missing or empty output during visibility as failure. Measure localization, correct-following fraction, recovery proportion/time, sustained duration, relapse, and absent-target false output. Diagnose ByteTrack motion prediction and association separately from SAM mask quality and drift. Plot paired time courses at actual annotation timestamps, not assumed consecutive video frames; summarize events within videos first.

### Cost and deliverables

Report detector calls, peak GPU memory, median FPS over three warmed-up synchronized runs, and correction/reset overhead. Timing includes decoding through ID generation, excluding loading, rendering, and scoring. Deliver manifests, configurations, predictions, baseline and paired results, recovery curves, and failure explanations. Report regressions and null outcomes, distinguishing local recovery effects from complete-system benefits.

## References

Cao et al. 2023. [Observation-Centric SORT: Rethinking SORT for Robust Multi-Object Tracking](https://arxiv.org/abs/2203.14360). CVPR.

Ding et al. 2025. [SAM2Long: Enhancing SAM 2 for Long Video Segmentation with a Training-Free Memory Tree](https://arxiv.org/abs/2410.16268). ICCV.

Luiten et al. 2020. [HOTA: A Higher Order Metric for Evaluating Multi-Object Tracking](https://arxiv.org/abs/2009.07736).

Ravi et al. 2024. [SAM 2: Segment Anything in Images and Videos](https://arxiv.org/abs/2408.00714).

Yang et al. 2024. [SAMURAI: Adapting Segment Anything Model for Zero-Shot Visual Tracking with Motion-Aware Memory](https://arxiv.org/abs/2411.11922).

Zhang et al. 2021. [ByteTrack: Multi-Object Tracking by Associating Every Detection Box](https://arxiv.org/abs/2110.06864).
