"""Video I/O and rendering; no model inference or remote connections here."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PALETTE = [(70, 210, 110), (255, 170, 50), (170, 90, 240), (40, 220, 240)]


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fit_size(width: int, height: int, max_side: int) -> tuple[int, int]:
    scale = min(1.0, max_side / max(width, height))
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def prepare_clip(source: Path, output: Path, limit: int, max_side: int, start: int):
    """Keep consecutive frames and native FPS. JPEGs give SAM its official input form."""
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Cannot open local video: {source}")
    frames = output / "frames"
    frames.mkdir()
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0:
        capture.release()
        raise ValueError("The video's FPS is missing/invalid; re-encode with a known frame rate.")
    original_size = [int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))]
    paths = []
    try:
        # Decode, do not rely on imprecise codec seeking to an arbitrary keyframe.
        for _ in range(start):
            if not capture.grab():
                raise ValueError("--start-frame is beyond the video.")
        for index in range(limit):
            ok, frame = capture.read()
            if not ok:
                break
            width, height = fit_size(frame.shape[1], frame.shape[0], max_side)
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            path = frames / f"{index:05d}.jpg"
            if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise OSError(f"Cannot write {path}")
            paths.append(path)
    finally:
        capture.release()
    if not paths:
        raise ValueError("No decodable frames in this video.")
    return paths, {"fps": fps, "frames": len(paths), "size": [width, height],
                   "original_size": original_size, "start_frame": start,
                   "sampling": "consecutive frames; resized once; JPEG quality 95; audio omitted"}


def read_frame(path: Path):
    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f"Unreadable frame: {path}")
    return frame


class VideoWriter:
    """Stream BGR frames to a bundled FFmpeg, producing browser-playable H.264."""
    def __init__(self, path: Path, size: tuple[int, int], fps: float):
        self.path, self.size = path, tuple(size)
        self.log = path.with_suffix(".ffmpeg.log").open("wb")
        self.process = subprocess.Popen([
            imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
            "-n", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(path)
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log)

    def write(self, frame):
        if (frame.shape[1], frame.shape[0]) != self.size:
            raise ValueError("Frame size changed during encoding.")
        self.process.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        try:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
            try:
                code = self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                raise RuntimeError(f"Video encoder timed out: {self.path}")
        finally:
            self.log.close()
        if code and error_type is None:
            raise RuntimeError(f"Video encoding failed; inspect {self.path.with_suffix('.ffmpeg.log')}")


def label_frame(frame, title: str, index: int):
    # Add a caption strip instead of hiding the top of the prediction image.
    result = cv2.copyMakeBorder(frame, 48, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 23, 28))
    cv2.putText(result, title, (12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.51, (245, 245, 245), 1, cv2.LINE_AA)
    cv2.putText(result, f"Frame {index}", (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (175, 185, 195), 1, cv2.LINE_AA)
    return result


def validate_box(box, width: int, height: int) -> list[float]:
    if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
        raise ValueError("Box must contain four finite numbers: x1 y1 x2 y2.")
    x1, y1, x2, y2 = map(float, box)
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"Box must fit the resized first frame ({width}x{height}) and have positive area.")
    return [x1, y1, x2, y2]


def overlay_mask(frame, mask, object_id: int, label: str):
    result = frame.copy()
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != frame.shape[:2]:
        raise ValueError("Mask must be aligned with the original lesson frame.")
    if not mask.any():
        return result
    color = PALETTE[(object_id - 1) % len(PALETTE)]
    result[mask] = (0.55 * result[mask] + 0.45 * np.array(color)).astype(np.uint8)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(result, contours, -1, color, 2)
    ys, xs = np.where(mask)
    cv2.putText(result, f"ID {object_id}: {label}", (int(xs.min()), max(64, int(ys.min()))),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
    return result


def mask_iou(prediction, target):
    """Undefined for two empty masks: return None, not misleading perfect accuracy."""
    p, t = np.asarray(prediction, dtype=bool), np.asarray(target, dtype=bool)
    if p.shape != t.shape:
        raise ValueError("Masks must have identical shapes.")
    union = np.logical_or(p, t).sum()
    return float(np.logical_and(p, t).sum() / union) if union else None
