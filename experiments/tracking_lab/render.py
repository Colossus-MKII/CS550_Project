"""Render saved predictions only. Never call a neural model or alter scores."""

import subprocess

import cv2
import imageio_ffmpeg
import numpy as np

from .common import CLASSES

COLORS = (
    (25, 207, 120),
    (255, 158, 30),
    (55, 145, 245),
    (219, 78, 200),
    (245, 210, 45),
    (80, 207, 220),
)


class VideoWriter:
    """Browser-playable H.264 at an explicitly artificial browsing frame rate."""

    def __init__(self, path, size, fps):
        self.log = path.with_suffix(".ffmpeg.log").open("wb")
        self.process = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{size[0]}x{size[1]}",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self.log,
        )

    def write(self, frame):
        self.process.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())

    def close(self):
        self.process.stdin.close()
        try:
            code = self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            raise RuntimeError("Video encoding timed out")
        finally:
            self.log.close()
        if code:
            raise RuntimeError("Video encoding failed; inspect FFmpeg log")


def overlay(rgb, objects):
    view = rgb.copy()
    for obj in objects:
        color = np.array(COLORS[(obj.identity - 1) % len(COLORS)][::-1])  # BGR
        view[obj.mask] = (view[obj.mask] * 0.55 + color * 0.45).astype(np.uint8)
        x, y, x2, y2 = np.rint(obj.box).astype(int)
        cv2.rectangle(view, (x, y), (max(x, x2 - 1), max(y, y2 - 1)), color.tolist(), 1)
        cv2.putText(
            view,
            f"{obj.category} #{obj.identity}",
            (max(0, x), max(16, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            color.tolist(),
            1,
            cv2.LINE_AA,
        )
    return view


def pixel_errors(rgb, gt, prediction):
    """Class-union pixel diagnostic, NOT an identity or instance scoring metric.

    A correctly covered pixel of each class is green; missing GT is blue; extra
    predicted foreground is red. Same-class identity swaps need the ID table.
    """
    correct = np.zeros(rgb.shape[:2], dtype=bool)
    missing = correct.copy()
    extra = correct.copy()
    for category in CLASSES:
        g = np.zeros_like(correct)
        p = np.zeros_like(correct)
        for obj in gt:
            if obj.category == category:
                g |= obj.mask
        for obj in prediction:
            if obj.category == category:
                p |= obj.mask
        correct |= g & p
        missing |= g & ~p
        extra |= p & ~g
    view = (rgb * 0.32).astype(np.uint8)
    view[correct] = (75, 150, 60)
    view[missing] = (245, 125, 45)
    view[extra] = (50, 70, 240)
    return view


def label(image, title):
    view = cv2.copyMakeBorder(
        image, 32, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 25, 30)
    )
    cv2.putText(
        view,
        title,
        (10, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (235, 240, 245),
        1,
        cv2.LINE_AA,
    )
    return view


def comparison(rgb, gt, a, b, t, diag_a, diag_b):
    def counts(key, diag):
        return f'{key} | FP {diag["FP"]} FN {diag["FN"]} | IDchg {diag["diagnostic_id_changes"]}'

    return np.vstack(
        [
            np.hstack(
                [
                    label(rgb, f"RGB | exported step {t}"),
                    label(overlay(rgb, gt), "Ground truth | IDs = channel + 1"),
                ]
            ),
            np.hstack(
                [
                    label(overlay(rgb, a), counts("A0 ByteTrack", diag_a)),
                    label(
                        pixel_errors(rgb, gt, a),
                        "A0 pixels: blue=miss, red=extra, green=covered",
                    ),
                ]
            ),
            np.hstack(
                [
                    label(overlay(rgb, b), counts("B0 SAM 2.1", diag_b)),
                    label(
                        pixel_errors(rgb, gt, b),
                        "B0 pixels: IDs are evaluated separately",
                    ),
                ]
            ),
        ]
    )
