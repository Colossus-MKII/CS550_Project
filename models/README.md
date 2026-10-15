# Model resources

For an English introduction to what each component does and how to review the proposed comparison, start with the [model study guide](../docs/model-guide/README.md).

Pretrained weights are stored in `models/checkpoints/` and ignored by Git. Download the RTX 3080 pilot set with:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1 -Models
```

The default set is:

| Local file | Role in proposal | Official source |
| --- | --- | --- |
| `yolo11s-seg.pt` | Shared, frozen detector/segmenter for A0/B0 and the paired history experiments | [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/) |
| `sam2.1_hiera_tiny.pt` | Required pretrained SAM 2.1 video propagation model | [Meta SAM 2](https://github.com/facebookresearch/sam2) |
| `sam2.1_hiera_small.pt` | Retained extra checkpoint; not part of the core comparison | [Meta SAM 2](https://github.com/facebookresearch/sam2) |
| `DeAOTB_PRE_YTB_DAV.pth` | Retained background resource; a complete SAM-Track setup also needs its SAM checkpoint and dependencies | [Official AOT/DeAOT model zoo](https://github.com/yoxu515/aot-benchmark/blob/main/MODEL_ZOO.md) |

The required baseline tracker is ByteTrack; its standard implementation requires no separate appearance-model checkpoint. It has historical motion state and track-management state, but no learned appearance-ReID feature in the selected baseline. The planned A-H/A-R experiments retain or reinitialize motion state; they do not train a tracker or replace its external target ID.

The B-H/B-R experiments retain or reinitialize SAM's target-specific inference state with the same correction prompt. Updating inference state is not weight training. All core experiments keep YOLO and SAM weights fixed. At most one simple automatic state-management policy may follow if the controlled evidence supports it; no new neural model or training stage is required.

MOG2, KNN and SAM-Track/DeAOT remain background resources. OC-SORT, SAM2Long and SAMURAI provide related work on motion-state errors, candidate histories, and memory selection; they are not additional required full-system baselines.

## Code and documentation

- YOLO segmentation/tracking: <https://docs.ultralytics.com/modes/track/>
- SAM 2.1 repository: <https://github.com/facebookresearch/sam2>
- OC-SORT: <https://arxiv.org/abs/2203.14360>
- SAM2Long: <https://arxiv.org/html/2410.16268v3>
- SAMURAI: <https://arxiv.org/html/2411.11922v2>
- Segment and Track Anything: <https://github.com/z-x-yang/Segment-and-Track-Anything>
- AOT/DeAOT implementation: <https://github.com/yoxu515/aot-benchmark>
- OpenCV background subtraction: <https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html>

Record the exact package versions and Git commit hashes once the implementation environments are created. Checkpoint downloads alone are not sufficient to reproduce an experiment.
