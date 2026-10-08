# CS550: Multi-Object Segmentation and Tracking

A semester research project comparing automatic segmentation and persistent object identities across different object categories. Vehicles are one category, alongside people and animals. The study measures mask accuracy, association stability, degradation under blur/brightness/compression, and processing cost.

**Status:** proposal and research starter. No datasets or weights have been downloaded, models trained, or benchmark results claimed. SAM3 training feasibility depends on the actual university GPU allocation and a measured pilot. The code supports YOLO inference; the SAM3 canonical-output adapter and numerical benchmark integrations remain implementation milestones.

## Proposal and study plan

- [Markdown proposal](docs/proposal.md)
- [Word proposal](output/docx/proposal.docx)
- [PDF proposal](output/pdf/proposal.pdf)
- [ACML LaTeX source](paper/proposal.tex)
- [Overleaf-ready source ZIP](output/latex/proposal_acml_source.zip)
- [Official template and provenance](templates/acml/README.md)
- [Compute feasibility](docs/compute_feasibility.md)
- [Experiment protocol](docs/experiment_protocol.md)
- [Eight-page report outline](docs/report_outline.md)
- [References](docs/references.md)
- [Experiment matrix](configs/study.json)
- [Hardware and fine-tuning gates](configs/hardware_gate.json)

The core comparison is pretrained **YOLO11s-seg + ByteTrack**, **YOLO11s-seg + BoT-SORT**, and **SAM3 with fixed category text prompts**. SAM3 image detector/segmenter fine-tuning is conditional; the native video tracker remains pretrained. If adaptation cannot fit the lab allocation or the mask/checkpoint pilot fails, fine-tune YOLO and compare both trackers instead. This is adaptation of an existing model, rather than a new tracking algorithm.

Team: **Jingdi Wu, Yupu Guo, Christina Ross**. Repository: [Colossus-MKII/CS550_Project](https://github.com/Colossus-MKII/CS550_Project).

The proposal is two pages including references, following chapter 1's two-page proposal requirement. The PDF is compiled with the unmodified `jmlr.cls` from the [official ACML 2026 conference-track template](https://www.acml-conf.org/2026/downloads/ACML_camera_ready.zip): single column, 11-point body, Computer Modern typography, and author-year citations. Its header identifies it as a CS550 course proposal; the supplied authors remain visible. The Word file is an editable companion approximating this layout, because the official ACML template is LaTeX. See [template provenance](templates/acml/README.md).

`docs/proposal.md` is the content source. Rebuild the Word companion, LaTeX, and source ZIP with `python -m pip install python-docx` and `python tools/build_proposal.py`. To reproduce the authoritative PDF, install Tectonic or use the source ZIP in Overleaf. With Tectonic:

```bash
mkdir -p tmp/acml_build
cp paper/proposal.tex templates/acml/jmlr.cls tmp/acml_build/
cd tmp/acml_build
tectonic --untrusted --keep-logs proposal.tex
cp proposal.pdf ../../output/pdf/proposal.pdf
cd ../..
```

The verified PDF was compiled with Tectonic 0.17.0. Standard TeX dependencies are supplied by the compiler. In Overleaf, upload the ZIP and select `proposal.tex` as the main document. Inspect both pages after rebuilding. Do not replace the official PDF with a Word export; Word and LaTeX can wrap text differently. Use the same ACML class for the later eight-page report, retaining the course's page limits rather than ACML's conference submission limit.

Select a shared category subset from publicly labeled YouTube-VIS training videos and divide complete sequences into training, validation, and internal evaluation sets. Freeze exact dataset category IDs, YOLO class IDs, text prompts, and video membership in versioned manifests before running experiments. Use no ground-truth test masks/boxes to initialize SAM3 in the automatic setting. Prompted tracking, if studied, must be a separate experiment. Tracking objects does not itself classify physical movement versus stationary objects when the camera moves.

## Quick start

Use Python **3.12+**. The dependency-free core can report hardware and validate records; image perturbations need Pillow. On a lab machine:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[vision]'
python -m unittest discover -s tests -v
cs550 hardware --output runs/hardware.json
```

The probe reports devices it can actually detect. It does not convert installed VRAM into a promise that fine-tuning fits. CPU execution is sufficient for preparation and unit tests. SAM3's official setup requires a CUDA GPU, Python >=3.12, PyTorch >=2.7, and CUDA >=12.6; CPU or Apple MPS training is outside that setup. See the [official SAM3 installation guide](https://github.com/facebookresearch/sam3#installation).

## YOLO baseline

Install the optional runner. Obtain an official YOLO11 segmentation checkpoint separately and place it under `weights/`; the runner requires a local checkpoint and local video/frame directory.

```bash
python -m pip install -e '.[yolo]'
cs550 yolo data/clip.mp4 --weights weights/yolo11s-seg.pt \
  --tracker configs/bytetrack.yaml --device 0 --classes 0 2 15 \
  --output runs/yolo_bytetrack
cs550 validate runs/yolo_bytetrack/predictions.jsonl
```

`--classes 0 2 15` selects COCO person, car, and cat classes; this command illustrates class filtering, not the final dataset category mapping. Use the frozen study manifest instead. Switch to `configs/botsort.yaml` for BoT-SORT. Its checked-in setting enables camera-motion compensation and disables appearance ReID, so it cannot silently add an extra appearance model. A CPU device can be selected with `--device cpu`. For a frame directory, filenames must sort chronologically and `--fps` is required. `--max-frames 100` is useful for a pilot, but truncated runs cannot be treated as full-video evaluations.

Each run saves `predictions.jsonl` and `metadata.json`: checkpoint SHA-256, complete package versions, tracker YAML, device, resolution, confidence, warmup count, elapsed time, and CUDA peak allocated/reserved memory when CUDA is used. End-to-end FPS includes association, mask transfer/RLE encoding, validation, and output writing; model loading and three prediction warmup passes are excluded. Repeat measurements on the same GPU and state the timing scope. CPU mask encoding is intentionally part of the measured pipeline and can limit this starter's throughput.

Training the fallback segmenter uses Ultralytics' official CLI after creating a valid YOLO segmentation dataset from **training sequences only**:

```bash
yolo segment train model=weights/yolo11s-seg.pt data=data/yolo_dataset.yaml \
  epochs=20 imgsz=640 batch=4 device=0 seed=550 project=runs name=yolo_ft
```

This is an example starting budget, not a tuned result. Choose the checkpoint and thresholds using validation videos; freeze them before final evaluation. See [YOLO segmentation training](https://docs.ultralytics.com/tasks/segment/) and [tracking](https://docs.ultralytics.com/modes/track/). ByteTrack/BoT-SORT settings are configuration tuning, distinct from training neural weights.

## SAM3 comparison and conditional fine-tuning

Use a separate upstream checkout and environment to avoid dependency conflicts. Request gated checkpoint access and authenticate according to the [official SAM3 README](https://github.com/facebookresearch/sam3). Then install upstream and open its official video notebook:

```bash
git clone https://github.com/facebookresearch/sam3.git vendor/sam3
cd vendor/sam3
python -m pip install -e '.[notebooks]'
git rev-parse HEAD
jupyter notebook examples/sam3_video_predictor_example.ipynb
```

Install a CUDA-compatible PyTorch build using upstream's current instructions first. Save the commit hash and exact checkpoint version. **Freeze SAM3 versus SAM3.1 explicitly:** newer upstream code/checkpoints exist; switching versions mid-study changes the experiment. The official notebook demonstrates video text prompts, propagation, and single/multi-GPU selection. For this study choose one GPU and fixed category prompts without interactive corrections. Export masks, native IDs, frame indices, and calibrated category mappings into the canonical schema below; a validated SAM3 adapter is still to be written and tested on the lab GPU. Running one session per category may multiply compute and requires category-namespaced IDs, so report the prompt policy and include all sessions in timing.

The [official training guide](https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md) includes a single-GPU image fine-tuning example:

```bash
python sam3/train/train.py \
  -c configs/roboflow_v100/roboflow_v100_full_ft_100_images.yaml \
  --use-cluster 0 --num-gpus 1
```

That command is **an upstream detection recipe, not a ready-made segmentation/MOTS training command**. Its [stock configuration](https://github.com/facebookresearch/sam3/blob/main/sam3/train/configs/roboflow_v100/roboflow_v100_full_ft_100_images.yaml) disables segmentation and comments out mask losses. Before any project fine-tuning: adapt an image configuration to mask annotations, enable segmentation and mask losses, verify the intended parameters receive finite gradients, then verify that checkpoint keys actually load into the inference detector/segmenter. A changed checkpoint file is insufficient if incompatible key prefixes leave inference weights unchanged. Keep the video tracker fixed and describe exactly which image/shared-encoder parameters were trained.

Run a **100-frame inference pilot** and **20 optimizer steps at batch size 1** before committing to a longer job. Record peak memory, step time, total GPU-hours estimate, and validation sanity checks. Smaller image resolution, frozen components, or gradient accumulation are possible experimental choices only when the adapted recipe supports them and masks remain valid. They do not guarantee the model fits. Use the YOLO fallback if the gate fails. No custom SAM3 training configuration is claimed to work in this repository yet.

## Robustness experiments

Extract the same ordered frames for every condition. Apply one corruption at a time; each preserves geometry so ground-truth masks and identities stay aligned:

```bash
cs550 perturb data/frames data/frames_blur \
  --spec '{"kind":"blur","radius":1.0}'
cs550 perturb data/frames data/frames_dim \
  --spec '{"kind":"brightness","factor":0.75}'
cs550 perturb data/frames data/frames_jpeg \
  --spec '{"kind":"jpeg","quality":50}'
```

Frames are read in lexicographic order and written as zero-padded PNGs. Ensure source ordering really is chronological. JPEG corruption performs exactly one lossy encode/decode; PNG output avoids adding a second lossy step. A manifest preserves source-to-output frame mapping and parameters. Compare each condition with a clean PNG export created using `{"kind":"clean"}`. Do not train on final evaluation corruptions or retune thresholds separately for each test condition.

## Canonical output and evaluation

One JSONL record per consecutive zero-based frame, including frames with no objects:

```json
{
  "frame_idx": 0,
  "timestamp_s": 0.0,
  "image_size": [2, 3],
  "objects": [{
    "object_id": 7,
    "category_id": 0,
    "category_name": "person",
    "score": 0.8,
    "mask": {"size": [2, 3], "counts": [1, 3, 2]}
  }]
}
```

This tiny mask is a schema example, not a model result. Masks are original-resolution binary **uncompressed COCO RLE in column-major order**, beginning with a background run. IDs are positive and unique within a frame; model category IDs must be mapped explicitly to benchmark IDs. YOLO detections without persistent IDs are omitted and counted in metadata. `validate` checks frame consecutiveness, dimensions, mask coverage, IDs, and scores.

The optional exporter produces one video's official VIS-format prediction entries with compressed RLE and absent-frame nulls:

```bash
python -m pip install -e '.[evaluation]'
cs550 export-vis runs/yolo_bytetrack/predictions.jsonl \
  --video-id 12 --frame-count 100 --category-map data/category_map.json \
  --output runs/yolo_bytetrack/vis_video12.json
```

Supply the actual benchmark video ID, exact frame count, and a JSON dictionary mapping model IDs as strings to positive dataset IDs. Aggregate entries across videos into one prediction array. Track confidence is the mean score over detected frames. The exporter rejects category changes within a track; adopt and document a validation-selected class-voting rule before exporting such tracks. Frame resolution and ordering must match the official annotations.

Compute **video AP** with the [official YouTube-VIS evaluator](https://github.com/youtubevos/vis), on a labeled internal held-out split as specified in the proposal. This exporter prepares predictions; it does not compute AP. **Mask-based HOTA/AssA**, ID switches, and per-frame mask AP need separately verified dataset adapters and matching rules; do not substitute bounding-box HOTA and label it mask HOTA. Use [TrackEval](https://github.com/JonathonLuiten/TrackEval) once the selected dataset adapter is validated. Recovery after occlusion should use annotated visibility/absence rules. Simple adjacent-mask differences confuse real motion with flicker.

## Reproducibility and verification

Commit the resolved experiment configuration, upstream model commit, checkpoint identifier/hash, split manifest, prompt/category mapping, seed, package snapshot, hardware report, and evaluator revision. The YOLO integration is pinned to an explicit Ultralytics release; Pillow/evaluation dependency ranges are resolved on installation, so save `python -m pip freeze` for each environment. SAM3 is installed from upstream separately and must be pinned to a recorded commit. Do not commit datasets, gated checkpoints, tokens, or large run outputs.

Local checks cover RLE orientation/round trips, invalid annotations, track/frame integrity, perturbation correctness/determinism, ordering, and overwrite protection. CI runs these checks on Python 3.12. **YOLO GPU inference, SAM3 inference/training, compressed VIS export against pycocotools, and numerical evaluator results remain unverified until the lab dependencies/GPU/data are available.** There are no fabricated benchmark tables.

This repository includes project scaffolding only; upstream packages/checkpoints retain their respective licenses. Review the [SAM license](https://github.com/facebookresearch/sam3/blob/main/LICENSE) and [Ultralytics licensing](https://www.ultralytics.com/license) before redistribution or non-course use.
