# 5. Reviewing the proposal with the model roles in mind

[Guide index](README.md) · [Previous: Evaluation metrics](04-evaluation-metrics.md) · [English proposal](../proposal/proposal.md) · [Chinese proposal](../proposal/proposal_zh.md)

This chapter is a technical reading aid, not a replacement proposal. It distinguishes what the current text commits to from decisions still needed before experiments. It does not certify that the software runs or that a GPU configuration is sufficient.

## What is coherent about the current plan?

The revised proposal preserves the systems question: how does detector-assisted temporal mask propagation compare with segmentation followed by box-based identity association? It adds the same recovery question to both: when a new observation arrives, does retained history help, or does reinitializing the target work better?

The October 15 revision connects A0/B0 comparison, error diagnosis, paired state interventions, and recovery curves. All core model weights remain fixed. At most one simple automatic state-management policy may follow if the evidence supports it. The controlled analysis is a deliverable even if neither strategy consistently improves the mean score.

The current text acknowledges that SAM 2.1 needs automatic prompts and that its wrapper affects results. It retains HOTA/DetA/AssA, IDF1, CLEAR diagnostics and detector-only AP, and adds fixed-target recovery proportion, time, duration and recurrence.

## The four history branches

| Branch | Historical state | Correction operation |
| --- | --- | --- |
| A-H | Retain ByteTrack motion state and uncertainty | Normal Kalman update from the correction box |
| A-R | Initialize new motion state | Same box, zero velocity, default initialization covariance |
| B-H | Retain SAM target history | Add the same corrective box prompt |
| B-R | Remove the target's previous prompts and inference history | Initialize it from the same box |

Each pair shares its own pre-correction run, external target ID, correction information and subsequent normal input schedule. A and B do not share identical internal states. Correct a target once, not twice through an intervention hook and the normal frame update. Do not actively reset other targets.

The ByteTrack implementation's `re_activate()` updates old state; its name does not imply reinitialization. In SAM, clearing points on a frame does not clear the target's visual history. A global predictor reset can erase every object, violating the target-level design. Test the exact state boundary and retain its code/configuration record.

ByteTrack has historical state, so A/B is not a memoryless-versus-memory comparison. A-H/A-R compare motion-state handling; B-H/B-R compare operational visual-state handling. Establish each pairwise effect first, then compare its conditions and duration across systems.

## A correction opportunity is not automatic re-identification

The diagnostic experiment explicitly routes the correction box to the intended target. Automatic A0/B0 must still detect, associate and manage targets themselves. If YOLO finds the correct dog after re-entry but B0 assigns it a new ID, a controlled correction may restore a mask while the automatic system still fragments identity. These are different failure stages.

Actual YOLO boxes and current-frame annotation-derived reference boxes are separate diagnostic conditions. Use no future annotations for inference. A reference box can still contain distracting pixels or objects and does not guarantee a perfect mask. After the one correction, normal prediction and association resume without annotation assistance.

The primary four-branch study uses common events where both pipelines retain usable target state. Separately count events with already-deleted tracks and other ineligible cases. Otherwise the study could hide failures for which retention is no longer possible.

## Decisions to resolve before freezing experiments

The following are review findings and proposed checks. They have not been implemented simply by writing this guide.

| Priority | Decision or risk | Why it affects the result | Required check or recorded choice |
| --- | --- | --- | --- |
| Core | SAM new-object and refresh logic | Duplicate births or wrong matches can dominate identity scores. | Specify assignment, candidate thresholds, duplicate suppression, refresh triggers, absence handling, and retirement. Test crossings and late arrivals. |
| Core | Category handling in ByteTrack | Class-aware scoring does not imply class-aware association. | Implement the proposal's per-category trackers with video-wide unique IDs and document this variant. |
| Core | Forward-only execution | Future prompts can influence earlier masks in an interactive predictor. | Introduce prompts chronologically and test that later prompts cannot change previously scored outputs. |
| Core | Detection schedule | Running YOLO every frame versus periodically changes both recall and cost. | Freeze each schedule on validation data and report detector-call counts. |
| Core | Track-to-mask export | A correct box ID attached to the wrong mask corrupts every downstream score. | Inspect multi-object exports; test missing detections and reordered predictions. |
| Core | Evaluation details | Different empty-mask, class, matching, or aggregation rules can change rankings. | Validate the shared format and evaluator with synthetic examples; specify all diagnostic thresholds. |
| Core | Data and event coverage | A fixed seed does not ensure useful recovery events or balanced coverage. | Freeze category counts and video/source grouping; check annotation density, event coverage and post-correction length. |
| Feasibility | Complete pipeline memory/runtime | Checkpoint size and GPU visibility do not establish feasibility. | Run short single-GPU pilots, then increase video length and object count. Measure total pipeline cost. |
| Core | Isolate H/R branches | Shared mutable state can erase the distinction or leak results between branches. | Clone or reconstruct equivalent pre-correction state; verify identical box input and independent subsequent updates. |
| Core | One-time, target-specific correction | Repeated annotation assistance would measure a different task. | Keep external IDs and other targets intact, process the correction once, then resume normal inputs and matching. |
| Core | Recovery definitions | Scoring only matched successes or the corrected frame can overstate recovery. | Fix the scoring target, exclude the correction frame, keep failures, and lock thresholds/windows on development/validation data. |
| Optional policy | Change one named rule | Simultaneous detector or association changes obscure what improved. | Keep all neural weights fixed; use only inference-time signals for at most one evidence-supported policy. |

## Fair comparison does not mean identical internals

It is reasonable for A to run detection each frame and B to use periodic discovery: these are different system designs. Fairness requires declaring that distinction, charging both systems for their actual work, and limiting conclusions accordingly.

The shared detector checkpoint within A0/B0 controls one factor, but does not equalize detection frequency, prompt representation, association, temporal memory, or effective internal image resolution. Consequently, this is not a controlled experiment isolating the SAM backbone. Compare A-R against A-H and B-R against B-H before analyzing cross-system patterns. A follow-up policy is compared with the corresponding unchanged baseline under the same other settings.

For re-entry cases, log whether an acceptable same-category detection exists at return and whether the original identity resumes. Review observation failures, association/lifecycle failures and post-correction failures separately. Annotation-based target routing belongs only to the explicitly controlled diagnostic experiment, not full automatic inference.

Both H/R branches keep their normal subsequent input streams: ByteTrack continues receiving detections and SAM continues its fixed automatic refresh schedule. No additional annotation corrections are supplied. Do not stop ByteTrack detections merely to mimic SAM's prompt interface. Differences across systems may still reflect how often observations arrive.

Plot paired recovery differences over time. Continued reliable observations may reduce history's influence, while another gap may expose it again; these are hypotheses, not guaranteed outcomes. Pre-correction true IoU is a diagnostic proxy, not an online policy input. Natural-scene groups can reveal associations but cannot alone isolate the causal role of every scene attribute.

## The data plan deserves an explicit audit

The proposal targets 200 labeled YouTube-VIS 2021 videos: 120 for development, 40 for validation, and 40 held out for evaluation. The subset helper names its development partition `train`; this does not require neural training. Use development/validation data for implementation, event design and parameter selection. Split complete videos before sampling frames, and freeze event rules, success criteria, windows and any automatic policy before held-out testing.

Before tuning, check the actual download and annotations, the five category mappings, the number of instances per category, late appearances, and identifiable common-source clips. A fixed random seed makes a selection reproducible, not automatically balanced or independent. Keep related source clips in the same split where this can be established.

The repository's [subset-selection helper](../../tools/select_ytvis_subset.py) is a starting point, not evidence that these checks have already passed. The planned counts are not a claim that the labeled dataset is fully downloaded. See [data setup notes](../../data/README.md).

Record event video/target, correction time, box source, available state and subsequent annotation timestamps. Aggregate multiple events within their source video before giving videos equal weight. Do not choose events after discovering which strategy wins.

## What implementation work remains even with frozen weights?

We still need compatible environments, model loading, preprocessing, prompt generation, track management, consistent output conversion, dataset manifests, evaluation, timing, and reproducible result storage. “No training required” does not mean “no engineering required.”

The detector-assisted SAM wrapper must introduce a second object after tracking begins and distinguish it from an existing one without ground-truth prompts or ByteTrack IDs in automatic inference. The four branches additionally require isolated state, one-time correction hooks and recovery evaluation. Existing lesson inference does not establish that these experiments are implemented.

Use a version and configuration manifest: checkpoint hash, upstream commit/package version, precision, resize rules, detector thresholds, track settings, discovery interval, mask threshold, offloading, correction metadata and reset boundaries. Checkpoint hashes are already recorded in the [resource inventory](../../resources/downloaded-resources.json); package, pipeline and event configurations still require their own records.

## A minimal feasibility sequence

1. **Inspect one frame:** confirm YOLO masks, classes, boxes, and image coordinates visually.
2. **Inspect one short sequence:** run pipeline A, checking two identities and an empty-detection frame.
3. **Test a prompted object:** verify SAM 2.1 propagation with an automatic detector box. A manual-prompt demonstration may help learning but is not an evaluation result.
4. **Test the wrapper:** add a late-arriving object; test a crossing, disappearance, and reappearance. Log ID creation and retirement.
5. **Test the evaluator:** use the synthetic cases in [Chapter 4](04-evaluation-metrics.md), then export one real sequence from both methods.
6. **Measure resources:** run the complete pipelines on the same validation clips and GPU, including detector/prompt overhead.
7. **Verify paired interventions:** branch one event into retain/reset runs; check state isolation, target-only reset, identical correction and continued normal inputs.
8. **Explore recovery:** review a small event set, compare time curves and failure stages, then define the final event and scoring rules.
9. **Freeze and evaluate:** finalize all settings on development/validation data, then evaluate held-out data without retuning. An automatic follow-up policy is included only if controlled evidence justified it before this stage.

This sequence is a recommended implementation plan, not a record of completed tests. Demo videos without benchmark annotations are appropriate for smoke tests but must not contribute quantitative accuracy scores.

The reported iLabU GPU visibility provides a place to investigate feasibility, not exclusive ownership of all visible GPUs or authorization to ignore resource limits. Use one GPU initially and the university's applicable scheduling/access rules. No larger training GPU purchase or allocation is justified by checkpoint sizes alone.

## Claims we can and cannot make

After completing the experiments, a defensible conclusion would be: “On our frozen five-category subset, under the stated automatic-prompt protocol, pipeline B achieved a different accuracy/cost tradeoff from pipeline A.” The direction and size of that difference must come from results.

The current design alone cannot establish that visual memory is universally better than motion state, that a better mask always preserves identity, or that controlled correction solves automatic re-identification. A positive local recovery effect may not improve the complete system if observation or association failures dominate. A real-time claim also requires measured end-to-end throughput under a defined workload.

No complete reproduction of OC-SORT, SAM2Long or SAMURAI is required. They inform the hypotheses and experimental interpretation: [OC-SORT](https://arxiv.org/abs/2203.14360), [SAM2Long](https://arxiv.org/html/2410.16268v3), [SAMURAI](https://arxiv.org/html/2411.11922v2).

## Five questions every team member should be able to answer

1. What history does ByteTrack retain, and how does it differ from SAM's state?
2. What exactly changes in A-R and B-R, and what stays the same within each pair?
3. Why does a correctly routed diagnostic correction not establish automatic re-identification?
4. How could mask overlap improve without identity continuity improving?
5. Which conclusions concern within-pipeline interventions, and which concern whole-system differences?

If the team agrees on these answers, reviewing the proposal becomes a discussion of concrete design choices rather than model names.
