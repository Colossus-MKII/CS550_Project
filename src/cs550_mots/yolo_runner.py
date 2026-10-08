"""Optional Ultralytics video inference, exporting full-resolution masks and IDs."""

import hashlib
import importlib.metadata
import json
import math
import platform
import time
from pathlib import Path

from .records import encode_rle, validate_frame


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_yolo(source, weights, output, tracker, device, imgsz, confidence,
             classes=None, fps=None, max_frames=None, warmup=3):
    try:
        import cv2
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("YOLO inference requires: python -m pip install -e '.[yolo]'") from exc

    source, weights, output = Path(source), Path(weights), Path(output)
    if not source.exists() or not weights.is_file():
        raise ValueError("source and local checkpoint must exist; this command does not download weights")
    if Path(tracker).suffix != ".yaml" or not Path(tracker).is_file():
        raise ValueError("provide an existing tracker YAML file")
    if not 0 <= confidence <= 1 or imgsz < 32 or warmup < 0:
        raise ValueError("require confidence in [0,1], imgsz >= 32, and warmup >= 0")
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be positive")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty to prevent overwriting a run")
    if source.is_dir():
        frames = sorted(p for p in source.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if not frames:
            raise ValueError("frame directory contains no supported images")
        if fps is None:
            raise ValueError("--fps is required for a frame directory")
        first_frame = cv2.imread(str(frames[0]))
    else:
        cap = cv2.VideoCapture(str(source))
        try:
            if fps is None:
                fps = cap.get(cv2.CAP_PROP_FPS)
            ok, first_frame = cap.read()
            if not ok:
                raise ValueError("cannot decode video")
        finally:
            cap.release()
    if fps is None or not math.isfinite(fps) or fps <= 0 or first_frame is None:
        raise ValueError("valid frame rate and decodable first frame are required")

    output.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "metadata.json"
    metadata = {
        "schema_version": 1, "status": "running", "source": str(source.resolve()),
        "weights": str(weights.resolve()), "weights_sha256": _sha256(weights),
        "tracker": str(Path(tracker).resolve()), "tracker_yaml": Path(tracker).read_text(),
        "device_requested": device, "imgsz": imgsz, "confidence": confidence,
        "classes": classes, "fps": fps, "warmup_prediction_passes": warmup,
        "precision_requested": "FP32", "max_frames": max_frames,
        "python": platform.python_version(),
        "packages": {distribution.metadata["Name"]: distribution.version
                     for distribution in importlib.metadata.distributions()},
        "timing_scope": "tracking + mask CPU transfer + validation + JSONL export; model load and prediction warmup excluded",
        "mask_encoding": "uncompressed COCO RLE, column-major",
        "untracked_detection_policy": "omit detections without IDs; count omitted detections",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))
    started = time.perf_counter()
    model = YOLO(str(weights))
    if model.task != "segment":
        raise ValueError("checkpoint must be a segmentation model")
    metadata["model_load_seconds"] = time.perf_counter() - started
    for _ in range(warmup):
        model.predict(first_frame, device=device, imgsz=imgsz, classes=classes,
                      conf=confidence, verbose=False, retina_masks=True, half=False)
    cuda_used = str(next(model.model.parameters()).device).startswith("cuda")
    if cuda_used:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()

    frame_count, omitted = 0, 0
    started = time.perf_counter()
    generator = model.track(source=str(source), tracker=tracker, stream=True, persist=True,
                            device=device, imgsz=imgsz, classes=classes, conf=confidence,
                            retina_masks=True, half=False, verbose=False, save=False)
    try:
        with (output / "predictions.jsonl").open("w") as handle:
            for frame_idx, result in enumerate(generator):
                height, width = (int(v) for v in result.orig_shape)
                objects = []
                boxes, masks = result.boxes, result.masks
                if boxes is not None and len(boxes):
                    if boxes.id is None:
                        omitted += len(boxes)
                    else:
                        if masks is None or len(masks.data) != len(boxes):
                            raise RuntimeError("tracked detections do not align with segmentation masks")
                        ids = boxes.id.detach().cpu().tolist()
                        categories = boxes.cls.detach().cpu().tolist()
                        scores = boxes.conf.detach().cpu().tolist()
                        binary_masks = masks.data.detach().cpu().numpy() > 0.5
                        for idx, object_id in enumerate(ids):
                            if binary_masks[idx].shape != (height, width):
                                raise RuntimeError("expected full-resolution masks from retina_masks=True")
                            category_id = int(categories[idx])
                            objects.append({"object_id": int(object_id), "category_id": category_id,
                                            "category_name": result.names[category_id],
                                            "score": float(scores[idx]),
                                            "mask": encode_rle(binary_masks[idx])})
                record = {"frame_idx": frame_idx, "timestamp_s": frame_idx / fps,
                          "image_size": [height, width], "objects": objects}
                validate_frame(record)
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
                frame_count += 1
                if max_frames is not None and frame_count >= max_frames:
                    break
    except Exception:
        metadata["status"] = "failed; partial predictions are not a completed run"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        raise
    finally:
        generator.close()
    if cuda_used:
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    metadata.update({"status": "complete", "frame_count": frame_count,
                     "elapsed_seconds": elapsed, "end_to_end_fps": frame_count / elapsed,
                     "omitted_untracked_detections": omitted, "cuda_used": cuda_used})
    if cuda_used:
        metadata.update({"peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
                         "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved()})
    metadata_path.write_text(json.dumps(metadata, indent=2))
    return metadata

