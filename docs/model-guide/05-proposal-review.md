# 5. Reviewing the proposal with the model roles in mind

[Guide index](README.md) · [Previous: Evaluation metrics](04-evaluation-metrics.md) · [English proposal](../proposal/proposal.md) · [Chinese proposal](../proposal/proposal_zh.md)

This chapter is a technical reading aid, not a replacement proposal. It distinguishes what the current text commits to from decisions still needed before experiments. It does not certify that the software runs or that a GPU configuration is sufficient.

## What is coherent about the current plan?

The revised proposal asks a meaningful systems question: does detector-assisted temporal mask propagation offer a better quality/cost tradeoff than segmentation followed by box-based identity association?

Its minimum deliverable is two pretrained pipelines, one fixed dataset subset, and one evaluation protocol. The October 13 revision adds a prioritized, feasibility-gated YOLO adaptation study: one validation-selected checkpoint feeds both A1/B1, compared with A0/B0 while preserving downstream settings. SAM stays frozen, and negative results remain valid outcomes. This retains the course feedback's pretrained-first safeguard while asking whether detector gains translate into tracking gains.

The current text acknowledges that SAM 2.1 needs automatic prompts and that its wrapper affects results. It specifies HOTA/DetA/AssA, IDF1, CLEAR diagnostics, and detector-only AP rather than judging success from one attractive mask or teaching clip.

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
| Core | Data independence and coverage | An internal split is not necessarily unseen to pretrained weights. | Audit source overlap where possible and report uncertainty. Freeze category counts and video/source grouping. |
| Feasibility | Complete pipeline memory/runtime | Checkpoint size and GPU visibility do not establish feasibility. | Run short single-GPU pilots, then increase video length and object count. Measure total pipeline cost. |
| Prioritized extension | YOLO adaptation controls | Head changes, leakage, or simultaneous threshold changes can obscure what improved. | Freeze training budget after a pilot, choose the checkpoint on validation data, reuse it in A1/B1, and document head/category changes and all results. |

## Fair comparison does not mean identical internals

It is reasonable for A to run detection each frame and B to use periodic discovery: these are different system designs. Fairness requires declaring that distinction, charging both systems for their actual work, and limiting conclusions accordingly.

The shared detector checkpoint within A0/B0 or A1/B1 controls one factor, but does not equalize detection frequency, prompt representation, association, temporal memory, or effective internal image resolution. Consequently, this is not a controlled experiment isolating the SAM backbone. Compare A1-A0 and B1-B0 separately, keeping each pair's downstream policies fixed.

If time permits after the core study, one small validation ablation could hold the discovery schedule fixed and vary a single integration choice. This is a possible follow-up, not another required experiment. Do not grow the project into a large grid before the two core systems work.

## The data plan deserves an explicit audit

The proposal targets 200 labeled YouTube-VIS 2021 training videos: 120 for the planned adaptation study, 40 for validation, and 40 held out for evaluation. The frozen minimum deliverable uses the latter 80. Fine-tuning proceeds after a feasibility pilot; resource-driven omissions must be documented. Split complete videos before sampling training frames, and never use held-out frames for training or checkpoint selection.

Before tuning, check the actual download and annotations, the five category mappings, the number of instances per category, late appearances, and identifiable common-source clips. A fixed random seed makes a selection reproducible, not automatically balanced or independent. Keep related source clips in the same split where this can be established.

The repository's [subset-selection helper](../../tools/select_ytvis_subset.py) is a starting point, not evidence that these checks have already passed. The planned counts are not a claim that the labeled dataset is fully downloaded. See [data setup notes](../../data/README.md).

Pretraining overlap is a separate question from our own split leakage. A model may have seen related material upstream even if we never tune on our evaluation partition. The DeAOT checkpoint's YouTube-VOS training history is a concrete reason to investigate; report unknowns rather than claim all evaluation clips are unseen. See [Chapter 3](03-sam-track-and-deaot.md).

## What implementation work remains even with frozen weights?

We still need compatible environments, model loading, preprocessing, prompt generation, track management, consistent output conversion, dataset manifests, evaluation, timing, and reproducible result storage. “No training required” does not mean “no engineering required.”

In particular, the proposal's most substantial custom component is likely the detector-assisted SAM wrapper. Before promising a full comparison, demonstrate that it can introduce a second object after tracking begins and distinguish it from an existing one without using ground-truth prompts or ByteTrack IDs.

Use a version and configuration manifest: checkpoint hash, upstream commit/package version, precision, resize rules, detector thresholds, track settings, discovery interval, mask threshold, and offloading options. Checkpoint hashes are already recorded in the [resource inventory](../../resources/downloaded-resources.json); package and pipeline configurations still require their own records.

## A minimal feasibility sequence

1. **Inspect one frame:** confirm YOLO masks, classes, boxes, and image coordinates visually.
2. **Inspect one short sequence:** run pipeline A, checking two identities and an empty-detection frame.
3. **Test a prompted object:** verify SAM 2.1 propagation with an automatic detector box. A manual-prompt demonstration may help learning but is not an evaluation result.
4. **Test the wrapper:** add a late-arriving object; test a crossing, disappearance, and reappearance. Log ID creation and retirement.
5. **Test the evaluator:** use the synthetic cases in [Chapter 4](04-evaluation-metrics.md), then export one real sequence from both methods.
6. **Measure resources:** run the complete pipelines on the same validation clips and GPU, including detector/prompt overhead.
7. **Freeze the protocol:** finalize settings on validation data, then evaluate the untouched internal evaluation split.

This sequence is a recommended implementation plan, not a record of completed tests. Demo videos without benchmark annotations are appropriate for smoke tests but must not contribute quantitative accuracy scores.

The reported iLabU GPU visibility provides a place to investigate feasibility, not exclusive ownership of all visible GPUs or authorization to ignore resource limits. Use one GPU initially and the university's applicable scheduling/access rules. No larger training GPU purchase or allocation is justified by checkpoint sizes alone.

## Claims we can and cannot make

After completing the experiments, a defensible conclusion would be: “On our frozen five-category subset, under the stated automatic-prompt protocol, pipeline B achieved a different accuracy/cost tradeoff from pipeline A.” The direction and size of that difference must come from results.

The current design alone cannot establish that SAM 2.1 is universally better at tracking, that a better mask always preserves identity, that the system recognizes any category, or that all test material was unseen during upstream pretraining. It also cannot establish a real-time claim until end-to-end throughput is measured under a defined workload.

## Five questions every team member should be able to answer

1. Which component decides that an object is a dog, and which component keeps its identity?
2. Where do SAM's prompts come from when a new object enters halfway through a video?
3. What happens when a track is temporarily absent but remains in memory?
4. How could a method have excellent mask IoU but poor IDF1?
5. Which conclusions concern the whole pipeline rather than an individual model?

If the team agrees on these answers, reviewing the proposal becomes a discussion of concrete design choices rather than model names.
