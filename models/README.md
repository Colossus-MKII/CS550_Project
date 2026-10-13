# Model resources

For an English introduction to what each component does and how to review the proposed comparison, start with the [model study guide](../docs/model-guide/README.md).

Pretrained weights are stored in `models/checkpoints/` and ignored by Git. Download the RTX 3080 pilot set with:

```powershell
powershell -ExecutionPolicy Bypass -File tools/download_project_resources.ps1 -Models
```

The default set is:

| Local file | Role in proposal | Official source |
| --- | --- | --- |
| `yolo11s-seg.pt` | Shared pretrained detector/segmenter for A0/B0 and initialization for the single YOLO fine-tune reused in A1/B1 | [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/) |
| `sam2.1_hiera_tiny.pt` | Required pretrained SAM 2.1 video propagation model | [Meta SAM 2](https://github.com/facebookresearch/sam2) |
| `sam2.1_hiera_small.pt` | Retained extra checkpoint; not part of the core comparison | [Meta SAM 2](https://github.com/facebookresearch/sam2) |
| `DeAOTB_PRE_YTB_DAV.pth` | Retained background resource, outside the October 13 experiment scope; a complete SAM-Track setup also needs its SAM checkpoint and dependencies | [Official AOT/DeAOT model zoo](https://github.com/yoxu515/aot-benchmark/blob/main/MODEL_ZOO.md) |

The required YOLO tracker is ByteTrack; its standard implementation requires no separate appearance-model checkpoint. BoT-SORT is outside the revised core scope.

MOG2, KNN, and additional pipelines are outside this revision. Their links and earlier downloads are retained as background resources. YOLO fine-tuning is the prioritized extension after pretrained baselines and a feasibility pilot; SAM 2.1 stays frozen in B0/B1. SAM/DeAOT training is out of scope.

## Code and documentation

- YOLO segmentation/tracking: <https://docs.ultralytics.com/modes/track/>
- SAM 2.1 repository: <https://github.com/facebookresearch/sam2>
- Segment and Track Anything: <https://github.com/z-x-yang/Segment-and-Track-Anything>
- AOT/DeAOT implementation: <https://github.com/yoxu515/aot-benchmark>
- OpenCV background subtraction: <https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html>

Record the exact package versions and Git commit hashes once the implementation environments are created. Checkpoint downloads alone are not sufficient to reproduce an experiment.
