"""Lessons 1-3: one frame's boxes/masks, then cross-frame ByteTrack identities."""
from contextlib import ExitStack
import json
import time

from .common import VideoWriter, label_frame, read_frame


def serialize_result(result, with_ids=False):
    rows = []
    if result.boxes is None:
        return rows
    for i, box in enumerate(result.boxes):
        class_id = int(box.cls.item())
        rows.append({"class_id": class_id, "class_name": result.names[class_id],
                     "confidence": float(box.conf.item()), "box_xyxy": box.xyxy[0].tolist(),
                     "track_id": int(box.id.item()) if with_ids and box.id is not None else None,
                     "mask_pixels": int((result.masks.data[i] > 0.5).sum().item()) if result.masks is not None else None})
    return rows


def select_prompts(detections, max_objects):
    """Top-scoring first-frame boxes only; class labels come from YOLO, never SAM."""
    candidates = sorted(detections, key=lambda row: row["confidence"], reverse=True)[:max_objects]
    return [{"object_id": i + 1, "label": row["class_name"], "box_xyxy": row["box_xyxy"],
             "confidence": row["confidence"], "frame": 0, "source": "YOLO first-frame box"}
            for i, row in enumerate(candidates)]


def run_yolo(paths, output, clip, args, device, checkpoint):
    from ultralytics import YOLO
    import torch

    # Separate model instances prevent the tracker's persistent state altering predict().
    detector, tracker = YOLO(str(checkpoint)), YOLO(str(checkpoint))
    names = {name: int(idx) for idx, name in detector.names.items()}
    if args.classes == "all":
        classes = None
    else:
        requested = [name.strip() for name in args.classes.split(",")]
        missing = set(requested) - names.keys()
        if missing:
            raise ValueError(f"Unknown YOLO class names: {sorted(missing)}")
        classes = [names[name] for name in requested]
    options = dict(device=device, imgsz=args.imgsz, conf=args.conf, classes=classes,
                   verbose=False, retina_masks=True)
    timers = {"yolo_predict_seconds": 0.0, "yolo_plus_bytetrack_seconds": 0.0}
    first_detections = None
    seen_ids = set()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    with ExitStack() as stack:
        render_size = (clip["size"][0], clip["size"][1] + 48)
        writers = {name: stack.enter_context(VideoWriter(output / f"{name}.mp4", render_size, clip["fps"]))
                   for name in ("01_boxes", "02_masks", "03_bytetrack")}
        records = stack.enter_context((output / "yolo_records.jsonl").open("w", encoding="utf-8"))
        for index, path in enumerate(paths):
            frame = read_frame(path)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            start = time.perf_counter()
            prediction = detector.predict(frame, **options)[0]
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            timers["yolo_predict_seconds"] += time.perf_counter() - start
            start = time.perf_counter()
            # persist=True associates THIS frame with earlier frames; not training.
            tracked = tracker.track(frame, persist=True, tracker="bytetrack.yaml", **options)[0]
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            timers["yolo_plus_bytetrack_seconds"] += time.perf_counter() - start
            detections, tracks = serialize_result(prediction), serialize_result(tracked, with_ids=True)
            if first_detections is None:
                first_detections = detections
            seen_ids.update(row["track_id"] for row in tracks if row["track_id"] is not None)
            records.write(json.dumps({"frame": index, "detections": detections, "tracks": tracks}) + "\n")
            # These are two displays of the SAME segmentation-model prediction,
            # not two separately trained detection/segmentation architectures.
            views = {"01_boxes": (prediction.plot(masks=False, line_width=2, font_size=12), "1. YOLO: boxes + class, no identity"),
                     "02_masks": (prediction.plot(boxes=False, masks=True), "2. YOLO: pixel masks, no identity"),
                     "03_bytetrack": (tracked.plot(line_width=2, font_size=12, color_mode="instance"), "3. YOLO + ByteTrack: masks + IDs")}
            for key, (view, title) in views.items():
                painted = label_frame(view, title, index)
                writers[key].write(painted)
                if index == len(paths) // 2:
                    import cv2
                    cv2.imwrite(str(output / f"{key}.jpg"), painted)
            if index % 20 == 0:
                print(f"YOLO / ByteTrack: {index + 1}/{len(paths)}", flush=True)
    stats = {**timers, "unique_track_ids": sorted(seen_ids), "first_frame_objects": len(first_detections or []),
             "timing_note": "Cold-start diagnostic, includes preprocessing/inference/postprocess. Excludes model loading, rendering and encoding; NOT benchmark FPS.",
             "cuda_peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20 if device.startswith("cuda") else None,
             "classes": args.classes, "confidence_threshold": args.conf}
    del detector, tracker
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return select_prompts(first_detections or [], args.max_objects), stats


def discover_first_frame(path, args, device, checkpoint):
    """Used when running just the SAM lesson with automatic initialization."""
    from ultralytics import YOLO
    import torch
    model = YOLO(str(checkpoint))
    names = {name: int(idx) for idx, name in model.names.items()}
    requested = [name.strip() for name in args.classes.split(",")]
    if args.classes != "all" and any(name not in names for name in requested):
        raise ValueError("Unknown --classes; use COCO names or 'all'.")
    classes = None if args.classes == "all" else [names[name] for name in requested]
    result = model.predict(read_frame(path), device=device, imgsz=args.imgsz, conf=args.conf,
                           classes=classes, verbose=False, retina_masks=True)[0]
    prompts = select_prompts(serialize_result(result), args.max_objects)
    del model, result
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return prompts
