"""Run the portable A0/B0 experiment on an allocated CUDA device.

Read this file first: each numbered stage calls one narrowly scoped module.
Usage: python -m tracking_lab.run --check
The output directory must be new; existing experiments are never overwritten.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
import traceback
import uuid

from . import ROOT, PACKAGE_ROOT, configure_runtime
from .common import CLASSES, digest, save_predictions, write_json
from .dataset import input_provenance, load_ground_truth, read_manifest

from .runtime import checked_weight, environment


def execute(args):
    import numpy as np
    import torch
    from .evaluate import evaluate_all, self_checks, metric_objects
    from .detector import detect_video
    from .bytetrack import run_bytetrack
    from .sam_baseline import run_sam
    from .diagnose import diagnose

    # 1. Validate dependencies, evaluation rules, weights and exact input files.
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config["seed"] != 550:
        raise ValueError("This reviewed pilot fixes seed 550")
    configure_runtime()
    env = environment(args.device, config["seed"])
    metrics = metric_objects(args.trackeval_root)
    checks = self_checks(metrics)
    yolo_path, yolo_sha = checked_weight(
        "yolo11s-seg.pt", args.weights_dir, args.weight_manifest
    )
    sam_path, sam_sha = checked_weight(
        "sam2.1_hiera_tiny.pt", args.weights_dir, args.weight_manifest
    )
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    videos, records, source = read_manifest(args.samples, selection["video_ids"])
    if args.check:
        print(
            json.dumps(
                {
                    "status": "preflight_passed",
                    "environment": env,
                    "videos": len(videos),
                    "frames": sum(len(v.rgb_paths) for v in videos),
                    "data_root": str(args.samples.resolve()),
                    "weights": [yolo_sha, sam_sha],
                    "evaluator_self_checks": checks,
                },
                indent=2,
            )
        )
        return None
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(
            "Choose a NEW output folder; completed or partial runs are preserved"
        )
    output.mkdir(parents=True)
    started = time.perf_counter()
    summary = {
        "status": "running",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": env,
        "configuration": config,
        "classes": list(CLASSES),
        "selection": selection,
        "samples_root": str(args.samples.resolve()),
        "weights": {
            "YOLO": {"sha256": yolo_sha, "file": yolo_path.name},
            "SAM": {"sha256": sam_sha, "file": sam_path.name},
        },
        "sample_manifest_sha256": digest(args.samples / "manifest.json"),
        "data_root_relative_to_run": Path(
            os.path.relpath(args.samples.resolve(), output)
        ).as_posix(),
        "trackeval_revision": "12c8791b303e0a0b50f753af204249e622d0281a",
        "sam_cpu_offload_guard": "CUDA fence before CPU prompt-mask consolidation; sam_io.py",
        "source_files": {
            path.name: digest(path) for path in sorted(PACKAGE_ROOT.glob("*.py"))
        },
        "limitations": [
            "Development pilot only, not held-out benchmark conclusions.",
            "Source FPS/timestamps unavailable; all temporal parameters are exported steps.",
            "Cached detector observations shared by both pipelines; no end-to-end FPS benchmark.",
            "No H/R interventions or standalone YOLO AP sweep in this first stage.",
        ],
        "videos": {},
    }
    write_json(output / "summary.json", summary)
    write_json(output / "config.json", config)
    write_json(output / "evaluator-self-checks.json", checks)
    write_json(
        output / "input-manifest.json", input_provenance(videos, records, source)
    )
    code = output / "code"
    code.mkdir()
    for name in summary["source_files"]:
        shutil.copyfile(PACKAGE_ROOT / name, code / (name + ".txt"))
    print("Output:", output, flush=True)
    try:
        # 2. Freeze YOLO observations. Both systems use exactly this cache.
        from ultralytics import YOLO

        detector = YOLO(str(yolo_path))
        all_detections = {}
        all_a = {}
        torch.cuda.reset_peak_memory_stats()
        for video in videos:
            folder = output / str(video.video_id)
            observations, stats = detect_video(
                detector, video, config, device=args.device
            )
            save_predictions(folder / "YOLO", observations, (video.height, video.width))
            all_detections[video.video_id] = observations
            # 3. ByteTrack has no GPU model or pixel decoder of its own.
            a, trace = run_bytetrack(observations, (video.height, video.width), config)
            all_a[video.video_id] = a
            save_predictions(folder / "A0", a, (video.height, video.width))
            write_json(folder / "A0/state-trace.json", trace)
            summary["videos"][str(video.video_id)] = {
                "frames": len(observations),
                "size": [video.width, video.height],
                "detector": stats,
                "A0_detector_calls_used": len(observations),
            }
        summary["yolo_peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 2**20
        del detector
        torch.cuda.empty_cache()

        # 4. SAM consumes RGB plus PERIODIC YOLO boxes, never GT/channel labels.
        from sam2.build_sam import build_sam2_video_predictor

        predictor = build_sam2_video_predictor(
            "configs/sam2.1/sam2.1_hiera_t.yaml",
            str(sam_path),
            device=args.device,
            apply_postprocessing=True,
        )
        predictor.fill_hole_area = (
            0  # Optional custom CUDA cleanup unavailable on Windows.
        )
        predictor.add_all_frames_to_correct_as_cond = True
        torch.cuda.reset_peak_memory_stats()
        all_b = {}
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            for video in videos:
                torch.cuda.synchronize()
                start = time.perf_counter()
                b, events, stats = run_sam(
                    predictor, video, all_detections[video.video_id], config
                )
                torch.cuda.synchronize()
                stats["diagnostic_seconds"] = time.perf_counter() - start
                all_b[video.video_id] = b
                folder = output / str(video.video_id)
                save_predictions(folder / "B0", b, (video.height, video.width))
                write_json(folder / "B0/event-log.json", events)
                write_json(folder / "B0/run-stats.json", stats)
                summary["videos"][str(video.video_id)]["B0"] = stats
                write_json(output / "summary.json", summary)
                print("Completed B0 video", video.video_id, flush=True)
        summary["sam_peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 2**20
        del predictor
        torch.cuda.empty_cache()

        # 5. ONLY NOW load GT. No inference function has accepted a GT argument.
        evaluation = {"A0": {}, "B0": {}}
        for video, record in zip(videos, records):
            gt = load_ground_truth(args.samples, record)
            for method, pred in [
                ("A0", all_a[video.video_id]),
                ("B0", all_b[video.video_id]),
            ]:
                evaluation[method][str(video.video_id)] = (gt, pred)
                frames, diagnostic = diagnose(gt, pred, all_detections[video.video_id])
                write_json(
                    output / str(video.video_id) / method / "diagnostics.json",
                    {"summary": diagnostic, "frames": frames},
                )
        scores = {
            method: evaluate_all(values, metrics)
            for method, values in evaluation.items()
        }
        write_json(output / "metrics.json", scores)
        summary["status"] = "inference_and_scoring_completed"
        summary["wall_seconds_inference_scoring"] = time.perf_counter() - started
        write_json(output / "summary.json", summary)
        print(
            "Scores:",
            json.dumps({method: s["macro"] for method, s in scores.items()}, indent=2),
            flush=True,
        )
        print(
            'Render with: python -m tracking_lab.report --output "' + str(output) + '"',
            flush=True,
        )
        return output
    except Exception:
        summary["status"] = "failed"
        summary["error"] = traceback.format_exc()
        write_json(output / "summary.json", summary)
        raise


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=PACKAGE_ROOT / "defaults/stage1.json"
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=PACKAGE_ROOT / "defaults/stage1_selection.json",
    )
    parser.add_argument(
        "--data-root",
        "--samples",
        dest="samples",
        type=Path,
        default=ROOT / "data/stage1",
    )
    parser.add_argument("--weights-dir", type=Path, default=ROOT / "checkpoints")
    parser.add_argument(
        "--weight-manifest",
        type=Path,
        default=PACKAGE_ROOT / "defaults/checkpoints.json",
    )
    parser.add_argument(
        "--trackeval-root", type=Path, default=ROOT / "external/TrackEval"
    )
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="Logical allocated CUDA device; respects CUDA_VISIBLE_DEVICES",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate GPU, versions, inputs, weights and evaluator without model inference",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "runs"
        / (
            "stage1-"
            + datetime.now().strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:6]
        ),
    )
    return parser


def main(argv=None):
    execute(make_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
