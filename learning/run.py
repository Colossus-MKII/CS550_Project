"""Run with: .venv/Scripts/python.exe -m learning.run --lesson all

Only local files and the local CPU/GPU are used. No SSH, dataset login, training,
automatic model downloads, or formal accuracy claims are part of this runner.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
# Avoid writing Ultralytics settings into the user's global profile.
os.environ["YOLO_CONFIG_DIR"] = str(ROOT / "outputs" / "learning" / ".ultralytics")
os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true", help="Check local dependencies/GPU/resources without loading models")
    p.add_argument("--video", type=Path, default=ROOT / "data/pilot/videos/01_dog.mp4")
    p.add_argument("--lesson", choices=["all", "yolo", "sam2"], default="all")
    p.add_argument("--max-frames", type=int, default=60, help="1-180 consecutive frames; keep first pilots short")
    p.add_argument("--start-frame", type=int, default=0)
    p.add_argument("--max-side", type=int, default=640, help="Resize source frames, 128-1280; SAM encoder remains 1024")
    p.add_argument("--imgsz", type=int, default=640, help="YOLO inference size (multiple of 32)")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--classes", default="person,dog,cat,horse,car", help="Comma-separated COCO class names, or all")
    p.add_argument("--conf", type=float, default=0.1, help="Low detection threshold preserves ByteTrack's low-score stage")
    p.add_argument("--max-objects", type=int, default=2, help="1-4 first-frame SAM targets, highest confidence first")
    prompt = p.add_mutually_exclusive_group()
    prompt.add_argument("--box", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"), help="Manual box on resized first frame")
    prompt.add_argument("--pick-box", action="store_true", help="Drag a box in an OpenCV window; Enter confirms, Esc cancels")
    p.add_argument("--open", action="store_true", help="Open the local HTML report after completion")
    return p


def environment(device_choice):
    import torch
    cuda = torch.cuda.is_available()
    if device_choice == "cuda" and not cuda:
        raise RuntimeError("CUDA requested, but PyTorch cannot access a local GPU. Run --check or choose --device cpu.")
    device = "cuda:0" if cuda and device_choice != "cpu" else "cpu"
    versions = {}
    for name in ["torch", "torchvision", "ultralytics", "SAM-2", "opencv-python", "numpy", "lap", "hydra-core"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT INSTALLED"
    try:
        sam_source = json.loads(importlib.metadata.distribution("SAM-2").read_text("direct_url.json") or "null")
    except importlib.metadata.PackageNotFoundError:
        sam_source = None
    return {"python": sys.version, "versions": versions, "cuda_available": cuda,
            "torch_cuda_runtime": torch.version.cuda, "device": device,
            "device_name": torch.cuda.get_device_name(0) if device.startswith("cuda") else "CPU",
            "sam2_install_source": sam_source,
            "expected_sam2_source_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4"}


def checked_weight(name):
    from .common import sha256
    path = ROOT / "models" / "checkpoints" / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run tools/download_project_resources.ps1 -Models first.")
    manifest = json.loads((ROOT / "resources/downloaded-resources.json").read_text(encoding="utf-8-sig"))
    expected = next((row["SHA256"] for row in manifest if row["File"] == f"models/checkpoints/{name}"), None)
    digest = sha256(path)
    if not expected or digest.lower() != expected.lower():
        raise RuntimeError(f"Checkpoint SHA-256 mismatch or missing manifest entry: {name}. Do not load untrusted .pt files.")
    return path, digest


def execute(args):
    import cv2
    import torch
    from .common import VideoWriter, prepare_clip, read_frame, validate_box, write_json
    from .report import make_comparison, write_report

    env = environment(args.device)
    if args.check:
        print(json.dumps(env, indent=2))
        missing = [key for key, value in env["versions"].items() if value == "NOT INSTALLED"]
        print("Pilot videos:", len(list((ROOT / "data/pilot/videos").glob("*.mp4"))))
        for name in ["yolo11s-seg.pt", "sam2.1_hiera_tiny.pt"]:
            path, _ = checked_weight(name)
            print("Verified checkpoint:", path.name)
        if missing:
            raise RuntimeError(f"Missing dependencies: {missing}. Run learning/setup.ps1.")
        return 0
    if not 1 <= args.max_frames <= 180 or not 1 <= args.max_objects <= 4:
        raise ValueError("Learning safety limits: --max-frames 1-180, --max-objects 1-4.")
    if not 128 <= args.max_side <= 1280 or not 32 <= args.imgsz <= 1280 or args.imgsz % 32:
        raise ValueError("Use max-side 128-1280 and imgsz 32-1280 in multiples of 32.")
    if args.start_frame < 0 or not 0 < args.conf < 1:
        raise ValueError("Use a nonnegative start frame and 0 < conf < 1.")
    source = args.video.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Local video not found: {source}")
    if args.lesson == "yolo" and (args.box or args.pick_box):
        raise ValueError("Box prompts are for --lesson sam2 or all, not the YOLO-only lesson.")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.manual_seed(550)
    Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
    output = ROOT / "outputs/learning" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    output.mkdir(parents=True, exist_ok=False)
    summary = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
               "source": str(source), "purpose": "local educational inference, NOT benchmark", "environment": env,
               "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}}
    packages = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    (output / "environment.txt").write_text("\n".join(packages) + "\n", encoding="utf-8")
    print(f"Output: {output}\nDevice: {env['device_name']}", flush=True)
    started = time.perf_counter()
    try:
        paths, clip = prepare_clip(source, output, args.max_frames, args.max_side, args.start_frame)
        summary["clip"] = clip
        with VideoWriter(output / "source.mp4", tuple(clip["size"]), clip["fps"]) as writer:
            for path in paths:
                writer.write(read_frame(path))
        yolo_path = sam_path = None
        summary["checkpoint_sha256"] = {}
        if args.lesson != "sam2" or not (args.box or args.pick_box):
            yolo_path, digest = checked_weight("yolo11s-seg.pt")
            summary["checkpoint_sha256"][yolo_path.name] = digest
        if args.lesson != "yolo":
            sam_path, digest = checked_weight("sam2.1_hiera_tiny.pt")
            summary["checkpoint_sha256"][sam_path.name] = digest
        prompts = []
        if args.lesson in {"yolo", "all"}:
            from .yolo_lessons import run_yolo
            prompts, summary["yolo"] = run_yolo(paths, output, clip, args, env["device"], yolo_path)
        if args.lesson in {"sam2", "all"}:
            box = args.box
            if args.pick_box:
                print("Drag a box on the first frame; Enter confirms, Esc cancels.", flush=True)
                x, y, w, h = cv2.selectROI("SAM prompt: drag box, Enter to confirm", read_frame(paths[0]), showCrosshair=True)
                cv2.destroyAllWindows()
                if not w or not h:
                    raise ValueError("Manual prompt cancelled; no SAM inference was run.")
                box = [x, y, x + w, y + h]
            if box is not None:
                prompts = [{"object_id": 1, "label": "selected object", "box_xyxy": validate_box(box, *clip["size"]),
                            "frame": 0, "source": "manual learning prompt (NOT automatic evaluation)"}]
            elif args.lesson == "sam2":
                from .yolo_lessons import discover_first_frame
                prompts = discover_first_frame(paths[0], args, env["device"], yolo_path)
            if not prompts:
                summary["sam2"] = {"status": "skipped", "reason": "No target in the first frame; use --pick-box or --classes all."}
                summary["status"] = "partial"
                print(summary["sam2"]["reason"], flush=True)
            else:
                from .sam2_lesson import run_sam2
                summary["sam2"] = run_sam2(paths, output, clip, prompts, env["device"], sam_path)
        make_comparison(output, clip)
        if summary["status"] == "running":
            summary["status"] = "completed"
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        summary["total_wall_seconds"] = time.perf_counter() - started
        write_json(output / "summary.json", summary)
        write_report(output, summary)
        print(f"Report: {output / 'index.html'}", flush=True)
    if args.open:
        import webbrowser
        webbrowser.open((output / "index.html").as_uri())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(execute(parser().parse_args()))
    except (ImportError, ValueError, RuntimeError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
