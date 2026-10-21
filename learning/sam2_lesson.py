"""Lesson 4: introduce up to two objects, then propagate their masks forward.

This intentionally simple first-frame lesson is NOT the full proposal pipeline:
there is no periodic discovery, refresh, association or track retirement here.
"""
from contextlib import nullcontext
import json
import time

import cv2
import numpy as np

from .common import VideoWriter, label_frame, overlay_mask, read_frame, write_json


def run_sam2(paths, output, clip, prompts, device, checkpoint):
    import torch
    from sam2.build_sam import build_sam2_video_predictor

    if not prompts:
        raise ValueError("No first-frame YOLO object found. Use --pick-box, --box, --classes all, or another video/start frame.")
    write_json(output / "sam2_prompts.json", prompts)
    first = read_frame(paths[0])
    for prompt in prompts:
        x1, y1, x2, y2 = map(int, prompt["box_xyxy"])
        cv2.rectangle(first, (x1, y1), (x2, y2), (70, 210, 110), 2)
        cv2.putText(first, f"ID {prompt['object_id']}: {prompt['label']}", (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 210, 110), 2)
    cv2.imwrite(str(output / "sam2_prompt.jpg"), first)
    # Apply the official model config; do not reduce its internal 1024 encoder size.
    predictor = build_sam2_video_predictor(
        "configs/sam2.1/sam2.1_hiera_t.yaml", str(checkpoint), device=device,
        apply_postprocessing=True)
    # Keep the upstream stability/memory defaults, but do not call the optional
    # CUDA extension. The builder's postprocessing overrides take precedence over
    # extra Hydra options, so disable this one property on the constructed model.
    predictor.fill_hole_area = 0
    labels = {p["object_id"]: p["label"] for p in prompts}
    amp = torch.autocast("cuda", dtype=torch.bfloat16) if device.startswith("cuda") else nullcontext()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    init_start = time.perf_counter()
    propagation_seconds = 0.0
    count = 0
    with torch.inference_mode(), amp:
        # CPU frame/state offload limits VRAM on a 10 GB RTX 3080. It still uses RAM.
        state = predictor.init_state(str(paths[0].parent), offload_video_to_cpu=True, offload_state_to_cpu=True)
        for prompt in prompts:
            predictor.add_new_points_or_box(state, frame_idx=0, obj_id=prompt["object_id"],
                                            box=np.asarray(prompt["box_xyxy"], dtype=np.float32))
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        initialization_seconds = time.perf_counter() - init_start
        propagation = iter(predictor.propagate_in_video(state, start_frame_idx=0, reverse=False))
        render_size = (clip["size"][0], clip["size"][1] + 48)
        with VideoWriter(output / "04_sam2.mp4", render_size, clip["fps"]) as writer, \
                (output / "sam2_records.jsonl").open("w", encoding="utf-8") as records:
            for expected_index in range(len(paths)):
                start = time.perf_counter()
                index, object_ids, logits = next(propagation)
                if index != expected_index:
                    raise RuntimeError("SAM frame order does not match the prepared clip.")
                masks = (logits > 0.0).cpu().numpy()[:, 0]
                if device.startswith("cuda"):
                    torch.cuda.synchronize()
                propagation_seconds += time.perf_counter() - start
                frame, rows = read_frame(paths[index]), []
                for object_id, mask in zip(object_ids, masks):
                    object_id = int(object_id)
                    frame = overlay_mask(frame, mask, object_id, labels[object_id])
                    rows.append({"object_id": object_id, "label_from_prompt": labels[object_id],
                                 "mask_pixels": int(mask.sum()), "empty_mask": not bool(mask.any())})
                    if index in {0, len(paths) // 2, len(paths) - 1}:
                        cv2.imwrite(str(output / f"sam2_mask_f{index:05d}_id{object_id}.png"), mask.astype(np.uint8) * 255)
                frame = label_frame(frame, "4. SAM 2.1: prompted masks + IDs", index)
                writer.write(frame)
                records.write(json.dumps({"frame": index, "objects": rows}) + "\n")
                if index == len(paths) // 2:
                    cv2.imwrite(str(output / "04_sam2.jpg"), frame)
                count += 1
        propagation.close()
    stats = {"frames": count, "objects": len(prompts), "initialization_seconds": initialization_seconds,
             "propagation_seconds": propagation_seconds, "mask_logit_threshold": 0.0,
             "cuda_peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20 if device.startswith("cuda") else None,
             "precision": "bfloat16 autocast" if device.startswith("cuda") else "float32",
             "offload_video_to_cpu": True, "offload_state_to_cpu": True,
             "postprocessing": "custom CUDA connected-components cleanup disabled",
             "builder_apply_postprocessing": True, "fill_hole_area": 0,
             "timing_note": "Cold-start diagnostic. Initialization includes frame loading/encoding/prompts; propagation includes mask CPU transfer. Excludes rendering/video encoding. NOT comparable benchmark FPS.",
             "limitation": "First-frame prompts only. No late-object discovery, refresh, association or retirement. Not the full proposal pipeline."}
    del state, predictor
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return stats
