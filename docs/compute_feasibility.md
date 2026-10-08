# SAM 3 Compute Feasibility

Research checked on October 7 2026. University lab hardware and allocation remain unconfirmed. This is a planning assessment, not a measured resource guarantee.

## What official sources establish

- The [SAM 3 training guide](https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md) explicitly documents local single-GPU fine-tuning. Multiple H100s are not a universal requirement.
- The [example RF100 configuration](https://github.com/facebookresearch/sam3/blob/main/sam3/train/configs/roboflow_v100/roboflow_v100_full_ft_100_images.yaml) uses batch size one, 1008 input resolution, bfloat16, and a default multi-GPU launcher. Launcher defaults are examples, not minimum hardware specifications.
- This configuration builds an image model and disables segmentation by default. Its commented segmentation-loss alternative requires verification before a mask-training experiment.
- The released recipes cover image detection and shared-feature adaptation. They do not establish an out-of-the-box end-to-end video-tracker training workflow.
- The [main repository](https://github.com/facebookresearch/sam3) documents Python 3.12 or newer, PyTorch 2.7 or newer, and a CUDA-compatible GPU with CUDA 12.6 or newer for its setup. Approved Hugging Face checkpoint access is required.

No official universal VRAM minimum, training duration, or GPU-hour estimate was found. A GPU model alone is insufficient: precision, batch size, masks, image resolution, optimizer states, and sequence length change memory consumption.

## Resource interpretation

| Available setup | Planning decision |
| --- | --- |
| CPU-only laptop or a Mac without a supported CUDA GPU | Use for data preparation, documentation, and dependency-light verification. Arrange a CUDA environment for the documented SAM 3 workflow. |
| A single 24 GB CUDA GPU | Candidate for a small pilot. Do not promise that segmentation-enabled full adaptation will fit. |
| A single 40 to 80 GB CUDA GPU | More memory headroom for the pilot. Still measure memory and throughput before estimating a sweep. |
| Multiple GPUs with a lab allocation | Larger experiments may be possible; verify the actual scheduler and data budget. |

These are conservative planning judgments, not official minimum specifications. A repository discussion reports roughly 18 GB for one image-stage configuration, but this does not certify a segmentation or video-training requirement: [discussion 163](https://github.com/facebookresearch/sam3/issues/163).

## Pilot acceptance criteria

1. Record device, VRAM, driver, CUDA, PyTorch, storage, job time limit, and allocation.
2. Obtain weights through the official access workflow; do not store access tokens in this repository.
3. Pin upstream commit and checkpoint variant. Run approximately 100 video frames with fixed category prompts; measure peak allocated and reserved memory and end-to-end wall time.
4. Prepare a small supervised image-stage training sample with complete instance masks for the selected concept queries.
5. Run at least 20 optimizer steps at batch size one. Verify that segmentation is enabled, mask loss is nonzero, gradients are finite, and intended parameters change.
6. Save and reload the checkpoint. Inspect matching state-dictionary keys and coverage; compare intended adapted weights against the pretrained checkpoint and run one short video.
7. Set a training cap from measured steps per second and available allocation. Log any resolution or batch changes; never compare mismatched settings without documenting them.
8. If adaptation fails, retain pretrained SAM 3 when inference fits and fine-tune the smaller YOLO segmentation baseline by the end of week 3. If CUDA or SAM 3 inference is unavailable, complete the YOLO tracker/adaptation comparison and document the missing SAM 3 experiment.

The [checkpoint-loading discussion](https://github.com/facebookresearch/sam3/issues/606) motivates explicit key-coverage checks. Image-stage checkpoint layouts and video detector prefixes must be verified for the pinned version. A silently skipped checkpoint cannot support a fine-tuning claim.

## Scope boundaries

The proposal promises a pretrained multi-method comparison and a measured adaptation attempt. It does not promise training a new foundation model or its temporal tracker from scratch. Encoder freezing and LoRA are possible custom extensions, not documented official recipes assumed by the proposal. Consult the pinned source before implementing either.

## Licenses and provenance

SAM 3 uses the [SAM License](https://github.com/facebookresearch/sam3/blob/main/LICENSE); it is not the Apache 2.0 license used by SAM 2. Ultralytics uses AGPL-3.0 for its open-source distribution. Keep upstream licenses, weights, and data terms distinct. The project should store URLs and provenance rather than redistribute datasets or model checkpoints.
