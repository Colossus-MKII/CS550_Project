# CS550 Project Proposal

Proposal materials for **Evaluating Multi Object Segmentation and Tracking**.

**Authors:** Jingdi Wu, Yupu Guo, Christina Ross · Rutgers University · Fall 2026.

This repository contains the proposal and the files needed to rebuild it. The initial model implementation, experiment configurations, tests, and temporary outputs have been removed. Model execution, fine-tuning, and numerical evaluation are proposed future work; no benchmark results are claimed.

## Proposal files

- [Markdown proposal](docs/proposal.md)
- [Two-page ACL PDF](output/pdf/proposal.pdf)
- [LaTeX source](paper/proposal.tex) and [BibTeX references](paper/references.bib)
- [Overleaf-ready source package](output/latex/proposal_acl_source.zip)
- [Exact supplied ACL template and provenance](templates/acl/README.md)

The PDF uses the original `acl.sty` and `acl_natbib.bst` from the user-supplied `Association_for_Computational_Linguistics__ACL__conference.zip`, with the standard two-column A4 layout and named authors. The local input ZIP is preserved. The course requires a two-page proposal and an eight-page final report excluding references.

## Planned comparison

| Method family | Baseline configurations | Adapted configurations |
| --- | --- | --- |
| YOLO segmentation | YOLO11s-seg + ByteTrack; YOLO11s-seg + BoT-SORT | Fine-tuned YOLO segmenter evaluated under both trackers; fixed tracker settings for each weight comparison. |
| SAM 2 / SAM 2.1 | SAM 2.1 checkpoint, detector-generated box prompts, native temporal propagation | SAM 2.1 neural fine-tuning with explicitly recorded trainable components, conditional on a GPU and data-conversion pilot. |
| SAM-Track | SAM keyframe segmentation + DeAOT propagation, with periodic object discovery | DeAOT component fine-tuning with SAM frozen, conditional on upstream training integration and the compute pilot; discovery settings tuned separately. |
| OpenCV background subtraction | MOG2; KNN, each with foreground instance separation and persistent-ID association | Validation-tuned background and association settings plus online background adaptation; this is not neural fine-tuning. |

YOLO is the required learned-weight adaptation. All three neural families have planned pretrained/adapted comparisons, but SAM 2.1 and DeAOT training remain conditional on the unconfirmed university GPU allocation. The [official SAM 2 training example](https://github.com/facebookresearch/sam2/blob/main/training/README.md) assumes A100 80 GB GPUs and uses eight GPUs; that example does not establish a universal minimum. DeAOT adaptation uses its [upstream training framework](https://github.com/yoxu515/aot-benchmark), rather than claiming that SAM-Track has an integrated end-to-end trainer. The classical [OpenCV methods](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html) adapt their background model online and expose tuning parameters.

Automatic SAM and OpenCV pipelines share a frozen YOLO detector for target labels and initialization/separation. They retain their own mask propagation or foreground association; detector tracking IDs are not supplied. These dependencies and all discovery work count toward runtime. Ground-truth-initialized propagation results, if collected, will be presented separately from automatic discovery.

## Evaluation plan

Use a sequence-disjoint internal subset of [YouTube-VIS 2021](https://youtube-vos.org/dataset/vis/), covering people, dogs, cats, horses, and cars. Compare the same clips, frame timeline, categories, and perturbations. Report fixed- and moving-camera strata; camera motion is a stress test for background subtraction.

| Metric | What it diagnoses |
| --- | --- |
| sMOTSA | Joint mask quality, false positives, and identity-switch penalties. |
| Mask HOTA, DetA, AssA | Overall tracking performance with detection and association decomposed. |
| MOTSA | Detection and identity errors at the specified mask matching threshold. |
| MOTSP | Mean mask IoU over matched instances; interpret alongside recall. |
| Mask-matched IDF1 and ID switches | Identity consistency across the sequence. |
| False positives and false negatives | Spurious instances and missed targets. |
| Native video AP | Supplementary YouTube-VIS evaluation. |
| FPS, peak memory, training time | Processing and adaptation costs. |

Use validated mask-based matching and category/ignore handling, with consistent overlap resolution. The custom multicategory conversion must be checked before reporting numbers. These are **MOTS-style metrics on an internal YouTube-VIS subset**, not official KITTI-MOTS results. Metric definitions follow the [original MOTS paper](https://arxiv.org/abs/1902.03604) and [HOTA/TrackEval](https://github.com/JonathonLuiten/TrackEval). Robustness is measured through paired clean-to-corrupted changes under blur, brightness shifts, and JPEG compression, plus occlusion failure analysis.

## Rebuild the proposal

The builder uses only the Python standard library. Run:

```bash
python tools/build_proposal.py
```

This creates the LaTeX source and source ZIP. For the PDF, upload the ZIP to Overleaf and select `proposal.tex`, or install Tectonic and compile in a temporary directory:

```bash
proposal_build_dir=$(mktemp -d)
cp paper/proposal.tex paper/references.bib templates/acl/*.sty templates/acl/*.bst "$proposal_build_dir/"
tectonic --untrusted --keep-logs --outdir "$proposal_build_dir" "$proposal_build_dir/proposal.tex"
cp "$proposal_build_dir/proposal.pdf" output/pdf/proposal.pdf
rm -r "$proposal_build_dir"
```

The compiler supplies standard TeX dependencies. Inspect every page after rebuilding. Keep the original ACL template geometry and the course page limits.
