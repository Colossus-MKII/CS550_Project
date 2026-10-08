"""Command-line entry points with lazy optional dependencies."""

import argparse
import json
import sys
from pathlib import Path


def _jsonl(path):
    with Path(path).open() as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _perturb_folder(source, output, spec):
    from PIL import Image
    from .perturbations import apply_perturbation, validate_perturbation

    validate_perturbation(spec)
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError("source must be a directory of chronologically named frames")
    if output == source or source in output.parents:
        raise ValueError("output must not be inside the source folder")
    frames = sorted(p for p in source.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not frames:
        raise ValueError("no supported image frames")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output folder must be empty")
    output.mkdir(parents=True, exist_ok=True)
    mapping = []
    for idx, path in enumerate(frames):
        filename = f"{idx:08d}.png"
        with Image.open(path) as image:
            apply_perturbation(image, spec).save(output / filename, format="PNG")
        mapping.append({"frame_idx": idx, "source_filename": path.name, "output_filename": filename})
    manifest = {"status": "complete", "spec": spec, "ordering": "lexicographic source filename",
                "frame_count": len(mapping), "frames": mapping,
                "note": "PNG export preserves transformed pixels; JPEG condition includes one encode/decode only"}
    (output / "perturbation.json").write_text(json.dumps(manifest, indent=2))
    return {"frame_count": len(mapping), "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="CS550 segmentation/tracking research starter")
    commands = parser.add_subparsers(dest="command", required=True)
    hardware = commands.add_parser("hardware", help="Report available hardware without claiming training feasibility")
    hardware.add_argument("--output", type=Path)
    validate = commands.add_parser("validate", help="Validate canonical frame records")
    validate.add_argument("records", type=Path)
    perturb = commands.add_parser("perturb", help="Apply a fixed perturbation to an ordered frame folder")
    perturb.add_argument("source", type=Path)
    perturb.add_argument("output", type=Path)
    perturb.add_argument("--spec", required=True, help='JSON object, e.g. {"kind":"blur","radius":1.0}')
    yolo = commands.add_parser("yolo", help="Track local video/frame folder using a local segmentation checkpoint")
    yolo.add_argument("source", type=Path)
    yolo.add_argument("--weights", required=True, type=Path)
    yolo.add_argument("--output", required=True, type=Path)
    yolo.add_argument("--tracker", default="configs/bytetrack.yaml")
    yolo.add_argument("--device", default="cpu")
    yolo.add_argument("--imgsz", type=int, default=640)
    yolo.add_argument("--confidence", type=float, default=0.1)
    yolo.add_argument("--classes", type=int, nargs="+")
    yolo.add_argument("--fps", type=float)
    yolo.add_argument("--max-frames", type=int)
    yolo.add_argument("--warmup", type=int, default=3)
    vis = commands.add_parser("export-vis", help="Export one video's predictions for the official VIS evaluator")
    vis.add_argument("records", type=Path)
    vis.add_argument("--video-id", type=int, required=True)
    vis.add_argument("--frame-count", type=int, required=True)
    vis.add_argument("--category-map", type=Path, required=True)
    vis.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "hardware":
            from .hardware import hardware_report
            result = hardware_report()
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2))
        elif args.command == "validate":
            from .records import validate_frame
            count, last_idx = 0, -1
            for frame in _jsonl(args.records):
                validate_frame(frame)
                if frame["frame_idx"] != last_idx + 1:
                    raise ValueError("frame_idx must start at zero and be consecutive")
                count, last_idx = count + 1, frame["frame_idx"]
            if not count:
                raise ValueError("records file is empty")
            result = {"valid_frames": count}
        elif args.command == "perturb":
            result = _perturb_folder(args.source, args.output, json.loads(args.spec))
        elif args.command == "yolo":
            from .yolo_runner import run_yolo
            result = run_yolo(args.source, args.weights, args.output, args.tracker,
                              args.device, args.imgsz, args.confidence, args.classes,
                              args.fps, args.max_frames, args.warmup)
        else:
            from .evaluation import export_vis
            if args.output.exists():
                raise ValueError("output already exists")
            mapping = json.loads(args.category_map.read_text())
            predictions = export_vis(_jsonl(args.records), args.video_id, args.frame_count, mapping)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(predictions))
            result = {"exported_tracks": len(predictions), "output": str(args.output),
                      "metrics": "not computed; run the official evaluator"}
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
