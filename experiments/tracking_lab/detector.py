"""Frozen YOLO observation cache shared by A0 and B0.

No tracking or annotations enter this module. We run once per RGB frame so the
two systems receive numerically identical detector outputs at shared call times.
B0 reads only every discovery_interval-th cached observation. Cache runtime is
not an end-to-end speed benchmark of either system.
"""

import time

import cv2
import numpy as np

from .common import CLASSES, COCO, Instance


def detect_video(model, video, config, device="cuda:0"):
    import torch

    frames = []
    seconds = 0.0
    for t, path in enumerate(video.rgb_paths):
        rgb = cv2.imread(str(path))  # Ultralytics ndarray input expects BGR.
        if rgb is None:
            raise ValueError(f"Unreadable RGB: {path}")
        torch.cuda.synchronize()
        start = time.perf_counter()
        result = model.predict(
            rgb,
            device=device,
            imgsz=config["imgsz"],
            conf=config["detector_conf"],
            iou=config["detector_nms_iou"],
            classes=list(COCO.values()),
            retina_masks=True,
            half=False,
            verbose=False,
        )[0]
        torch.cuda.synchronize()
        seconds += time.perf_counter() - start
        objects = []
        if len(result.boxes):
            if result.masks is None:
                raise RuntimeError(
                    "YOLO segmentation model returned boxes without masks"
                )
            masks = (result.masks.data > 0.5).cpu().numpy()
            if masks.shape[1:] != (video.height, video.width):
                raise RuntimeError("YOLO masks are not in source coordinates")
            for i, (box, mask) in enumerate(zip(result.boxes, masks)):
                category = result.names[int(box.cls.item())]
                if category not in CLASSES:
                    raise RuntimeError("Unexpected detector category")
                objects.append(
                    Instance(
                        i,
                        category,
                        box.xyxy[0].cpu().numpy().astype(np.float32),
                        mask,
                        float(box.conf.item()),
                    )
                )
        frames.append(objects)
        if t % 10 == 0:
            print(f"YOLO {video.video_id}: {t+1}/{len(video.rgb_paths)}", flush=True)
    return frames, {
        "diagnostic_inference_seconds": seconds,
        "actual_detector_calls": len(frames),
        "precision": "float32",
        "timing_scope": "synchronized cold diagnostic; excludes model loading, file decoding, rendering and evaluation; not benchmark FPS",
    }
