# Multi-Object Segmentation and Tracking: The Role of Historical State in Error Recovery

**Jingdi Wu, Yupu Guo, Christina Ross**  

Rutgers University · CS550 Massive Data Mining · Fall 2026  
Revised project proposal · October 15, 2026

## Abstract

We will compare YOLO11s-seg with ByteTrack and detector-assisted SAM 2.1 on a fixed YouTube-VIS 2021 subset, examining segmentation quality, identity continuity, and computational cost. Building on this comparison, we will study how historical state affects error recovery in both pipelines: when a new target observation becomes available, under what conditions is retaining the existing state or reinitializing it more effective, and how long do these effects persist?

With model weights fixed, we will compare retention and reset for ByteTrack's motion state and SAM's visual history, using identical corrective information and subsequent inputs within each pipeline. Paired comparisons, frame-level recovery curves, and failure cases will examine the relationship between historical reliability, new-observation quality, and scene changes. If reproducible and actionable patterns emerge, we will test whether one simple policy improves the complete automatic system.

## 1 Background and research questions

Object detection, segmentation, and identity association in video are related tasks with different sources of error. YOLO provides frame-level boxes, classes, and masks; ByteTrack maintains tracks through motion prediction and detection association; SAM 2.1 propagates target masks using prompts and visual memory.

Preliminary teaching experiments motivated us to distinguish these components. For example, a returning object receiving a new ID does not by itself justify detector fine-tuning. The failure could arise from a missed detection, incorrect association, track termination, or the influence of historical state on subsequent predictions.

Both ByteTrack and SAM use history, but store different information and use it differently. ByteTrack summarizes past observations as a motion state and an uncertainty estimate, whereas SAM uses visual information encoded from historical images and predicted masks. History can support prediction when reliable observations are temporarily unavailable, but it can also continue to influence a system after motion changes, incorrect associations, or mask drift.

We organize the project around how historical state and new observations jointly affect recovery:

- **RQ1: System performance and error sources.** How do the two automatic pipelines differ in segmentation, identity continuity, and computational cost, and where do their main failures occur?
- **RQ2: Conditional benefits of retention and reset.** Given identical corrective information, when does retaining history or reinitializing help? How do these differences relate to prediction quality before correction, new-observation quality, and scene changes?
- **RQ3: Recovery dynamics and practical relevance.** How long does the influence of historical state persist, can subsequent reliable observations remove it, and can the observed patterns inform a policy for the complete system?

We do not assume that either historical mechanism or recovery strategy is universally superior. Improvements, regressions, and negligible differences under different conditions are all research outcomes.

## 2 Related work

ByteTrack maintains trajectories by associating high- and low-confidence detections and uses Kalman filtering for motion prediction (Zhang et al., 2021). OC-SORT examines state-estimation errors under occlusion and nonlinear motion, using renewed observations to correct accumulated errors (Cao et al., 2023). These studies motivate an investigation of motion-state retention and recovery.

SAM 2 propagates masks for prompted targets using visual memory (Ravi et al., 2024). SAM2Long reduces error propagation through multiple candidate historical pathways and memory selection (Ding et al., 2025); SAMURAI uses motion consistency to guide candidate-mask and historical-memory selection (Yang et al., 2024). These studies show that the organization and use of history can affect tracking even when model weights are fixed.

We place these questions in a common recovery-experiment framework, examining the roles of motion state and visual history after a new observation becomes available. Our contribution is controlled comparison, analysis of applicable conditions, and system-level validation. We do not claim state reset or memory selection itself as a new algorithm, nor require complete reproduction of every related method.

## 3 Experimental design

### Automatic system baselines

We retain the two original pipelines:

- **A0: YOLO11s-seg + ByteTrack.** Run pretrained YOLO on every frame, associate detections with ByteTrack, and attach each ID to the corresponding instance mask. Use separate trackers per category and video-wide unique IDs.
- **B0: Detector-assisted SAM 2.1.** Use the same YOLO weights as A0 to provide periodic box prompts and classes, with frozen SAM 2.1 Hiera Tiny propagating the masks.

B0 matches detections one-to-one to the bounding boxes of same-category propagated masks using box IoU. A match refreshes the prompt while retaining target history; an accepted unmatched detection creates a new ID. Discovery intervals, duplicate suppression, prompt refresh, and lost-track retention rules are determined during development and validation.

B0 uses neither ByteTrack IDs nor ground-truth prompts. Neither baseline includes an explicit long-term appearance re-identification module. A0/B0 compare complete systems, including their detection frequencies and association rules; performance differences are not attributed directly to their historical-state representations.

### Failure localization and event selection

Using frame-level predictions and annotation review, we distinguish:

1. **Observation problems:** the target is not detected, or its detected class, location, or mask is inaccurate.
2. **Association and track-management problems:** an adequate detection exists but is not assigned to the correct target, or the original track has already terminated.
3. **State-update and subsequent-prediction problems:** a new observation has been provided for the corresponding target, but later prediction or association still deviates, or fails again after recovery.

Using predefined rules, select events from development and validation data covering stable tracking, occlusion, disappearance and re-entry, abrupt motion changes, and similar-object distractors. Events are not selected based on which recovery strategy ultimately performs better.

The primary four-group comparison uses common events for which both systems retain an operable target state. Cases that cannot support retention, such as already-deleted tracks, are recorded separately with their counts and proportions so that these real failures are not overlooked.

### Retention and reset experiments

At the correction time of an event, provide a box with an explicit correspondence to the target being recovered. The two branches within each pipeline share the same pre-correction execution history and receive the same corrective box and accompanying information.

| Group | Historical-state treatment | Corrective operation |
| --- | --- | --- |
| A-H | Retain ByteTrack motion state | Perform a normal Kalman update with the corrective box |
| A-R | Reinitialize ByteTrack motion state | Initialize position and size from the corrective box, zero velocities, and set covariance using the default initialization rule |
| B-H | Retain SAM target history | Add the same box prompt to the existing target |
| B-R | Rebuild SAM target inference state | Clear that target's old prompts, visual memory, and associated state, then initialize with the same box prompt |

A-H/A-R keep the same external ID, post-correction alive status, and lifecycle handling, changing only the defined treatment of the motion state. B-H/B-R likewise preserve the external ID and do not explicitly reset other targets. The reset scope differs between systems: conclusions concern each recovery strategy rather than treating the internal operations as identical.

Each branch consumes the corrective information once, avoiding duplicate updates in the same frame. Thereafter, prediction and association return to the system's own operation; annotations no longer repair target correspondence. Subsequent losses, ID changes, or tracking of the wrong target are scored as they occur.

Use two corrective-box sources and report them separately:

- **Actual YOLO detection boxes:** examine recovery with noisy detector inputs.
- **Reference boxes derived from the current frame's annotations:** provide an explicit corrective reference to analyze historical-state effects. A reference box can still contain background or other objects and does not guarantee correct segmentation.

Box-to-target correspondence is fixed manually in the mechanism experiment. This control asks whether the system can recover after receiving a correction opportunity; it does not imply that automatic re-identification has been solved. Report the fully automatic A0/B0 results separately, and retain the event's baseline trajectory without additional controlled correction as a reference.

### Unified analysis and system validation

After correction, both strategies within a pipeline receive the same normal input schedule: ByteTrack continues to receive frame-level detections, and SAM continues its predefined automatic prompt refreshes. No additional human or annotation-based corrections are supplied during the observation window.

First compare reset against retention within each pipeline, then compare the conditions and duration of benefits across pipelines. Examine:

- whether the pre-correction prediction has already deviated from the target;
- whether new observations are accurate and remain available;
- how occlusion, motion changes, and similar-object distractors affect recovery;
- whether later observations shrink or amplify the difference, or lead to repeated failures.

These factors explain outcomes; the initial study does not perform an exhaustive parameter search over every combination. Cross-pipeline differences may still reflect detection frequency, input format, and association method, and cannot alone establish that one memory mechanism is superior.

If stable, actionable patterns emerge, select at most one simple policy for the corresponding A or B pipeline and compare it with its original baseline. An automatic policy may use only inference-time signals, not ground truth to decide when to reset. If evidence is insufficient to support an improved policy, the complete paired experiments, recovery-dynamics analysis, and failure explanations remain the research outcome.

All core experiments freeze YOLO and SAM weights; detector fine-tuning is not introduced simultaneously.

## 4 Dataset and experimental controls

Retain the original target: select 200 annotated YouTube-VIS 2021 videos covering person, dog, cat, horse, and car, using the preprocessed Google Drive release linked by SlotCurri (Moon et al., 2026). Verify labeled-video and category coverage before confirming this target: the documented training export is video-only, while the validation export includes instance masks. With seed 550, split whole videos into 120 development, 40 validation, and 40 held-out evaluation videos. Keep clips from the same source together and split videos before extracting frames.

The development set supports implementation, pilot experiments, and candidate-rule exploration; validation supports diagnosis and configuration selection. Start the recovery study with a small event subset to verify correct implementation of the interventions and check scenario coverage, annotation density, and observation length. Freeze event rules, recovery criteria, and any automatic policy before inspecting held-out evaluation results.

All variants process identical ordered frames, share external resizing, and record internal preprocessing, precision, model versions, and parameters. Map outputs back to annotation coordinates and process time forward, without using future prompts to revise already-scored earlier outputs.

Within each pipeline's H/R pair, detection inputs and subsequent prompt schedules are identical, while the system's own predictions and associations may diverge. Use consistent post-correction windows, visibility handling, and time units. Report recovery at actual annotation timestamps and intervals rather than treating sampled annotation points as consecutive original frames.

Ground truth is used only for complete-system scoring, event diagnosis, and explicitly labeled reference-prompt experiments. Pre-correction box or mask quality is an offline proxy for historical reliability, not an input to the automatic policy. Correlations across natural-scene groups are not treated as causal evidence on their own.

## 5 Evaluation and expected outcomes

### Complete-system evaluation

Retain class-aware mask HOTA, DetA, AssA, IDF1 at mask IoU 0.5, and false-positive, false-negative, and ID-switch counts. Also report standalone YOLO box/mask AP50:95 to help separate detection and association problems.

Validate the evaluator with perfect predictions, deliberate misses, and deliberate ID switches. Aggregate videos within each class according to metric rules, then weight classes equally, retaining per-video results. HOTA, IDF1, and TrackEval provide the main evaluation basis (Luiten et al., 2020; Ristani et al., 2016; Luiten and Hoffhues, 2020).

### Recovery-dynamics evaluation

Both pipelines are evaluated on whether they continue to follow the designated target correctly after correction, including:

- target localization quality and the fraction of correct following while visible;
- the fraction of events reaching the predefined recovery criterion and time to recovery;
- the duration of sustained correct following after recovery and recurrence of errors;
- erroneous output while the target is not visible.

Primary scoring excludes the directly corrected frame. Keep target correspondence fixed rather than choosing the prediction with the largest annotation overlap anew on every frame. Missing or empty output while the target is visible counts as failure. Determine and lock localization thresholds, the required number of consecutive successful annotation timestamps, and observation windows during development and validation.

Add diagnostics appropriate to each pipeline's function:

- **ByteTrack:** motion-predicted box error, subsequent detection association, and identity errors. Resetting its state does not directly change masks already generated by YOLO, so mask quality alone cannot evaluate the intervention.
- **SAM:** mask IoU, drift, false foreground, and post-correction propagation quality.

Compute paired H/R differences for the same events and plot post-correction time courses to examine when differences appear, how long they persist, and whether they recur. Aggregate multiple events within a video before aggregating across videos so that event-rich videos do not dominate the results.

### Cost and deliverables

On the same GPU and inputs, report peak GPU memory, detector-call counts, and median FPS across three synchronized, warmed-up runs. End-to-end timing includes decoding, detection, prompt or state handling, segmentation, and ID generation; exclude model loading, rendering, and scoring. Separately report correction and reinitialization overhead.

Deliver split and event manifests, configurations and version records, complete predictions, A/B baseline results, the four controlled experiments, recovery curves, conditional analyses, failure cases, and any automatic-policy validation results.

The expected outcome is an account of when historical state helps or impedes recovery in the two pipelines and whether subsequent observations remove these effects. Report improvements, regressions, and negligible differences, distinguishing local mechanism findings from complete-system benefits.

## References

Jinkun Cao, Jiangmiao Pang, Xinshuo Weng, Rawal Khirodkar, and Kris Kitani. 2023. [Observation-Centric SORT: Rethinking SORT for Robust Multi-Object Tracking](https://arxiv.org/abs/2203.14360). CVPR.

Shuangrui Ding, Rui Qian, Xiaoyi Dong, Pan Zhang, Yuhang Zang, Yuhang Cao, Yuwei Guo, Dahua Lin, and Jiaqi Wang. 2025. [SAM2Long: Enhancing SAM 2 for Long Video Segmentation with a Training-Free Memory Tree](https://arxiv.org/abs/2410.16268). ICCV.

Jonathon Luiten, Aljosa Osep, Patrick Dendorfer, Philip Torr, Andreas Geiger, Laura Leal-Taixe, and Bastian Leibe. 2020. [HOTA: A Higher Order Metric for Evaluating Multi-Object Tracking](https://arxiv.org/abs/2009.07736). arXiv:2009.07736.

Jonathon Luiten and Arne Hoffhues. 2020. [TrackEval](https://github.com/JonathonLuiten/TrackEval). Evaluation software.

WonJun Moon, Hyun Seok Seong, and Jae-Pil Heo. 2026. [Reconstruction-Guided Slot Curriculum: Addressing Object Over-Fragmentation in Video Object-Centric Learning](https://github.com/wjun0830/SlotCurri). CVPR.

Nikhila Ravi et al. 2024. [SAM 2: Segment Anything in Images and Videos](https://arxiv.org/abs/2408.00714). arXiv:2408.00714.

Ergys Ristani, Francesco Solera, Roger Zou, Rita Cucchiara, and Carlo Tomasi. 2016. [Performance Measures and a Data Set for Multi-Target, Multi-Camera Tracking](https://arxiv.org/abs/1609.01775). ECCV Workshops.

Cheng-Yen Yang, Hsiang-Wei Huang, Wenhao Chai, Zhongyu Jiang, and Jenq-Neng Hwang. 2024. [SAMURAI: Adapting Segment Anything Model for Zero-Shot Visual Tracking with Motion-Aware Memory](https://arxiv.org/abs/2411.11922). arXiv:2411.11922.

Yifu Zhang, Peize Sun, Yi Jiang, Dongdong Yu, Fucheng Weng, Zehuan Yuan, Ping Luo, Wenyu Liu, and Xinggang Wang. 2021. [ByteTrack: Multi-Object Tracking by Associating Every Detection Box](https://arxiv.org/abs/2110.06864). arXiv:2110.06864.
