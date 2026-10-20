"""Read audited, lossless PNG exports of the actual SlotCurri arrays.

The preview export is an exact representation, not a teaching-video dataset:
RGB pixels are unchanged, and mask alpha equals segmentations[..., channel]>0.
Inference receives ONLY RGB paths. GT is loaded separately AFTER inference.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .common import CLASSES, Instance, digest, mask_box


@dataclass(frozen=True)
class VideoInput:
    video_id: int
    rgb_paths: tuple
    height: int
    width: int


def read_manifest(folder, ids):
    folder = Path(folder)
    data = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    records = {int(s["id"]): s for s in data["samples"]}
    if len(ids) != len(set(ids)):
        raise ValueError("Video IDs must be unique")
    videos = []
    selected = []
    for key in ids:
        row = records[key]
        paths = tuple(
            folder / str(key) / "rgb" / f"{t:05d}.png" for t in range(row["frames"])
        )
        if not paths or any(not p.is_file() for p in paths):
            raise ValueError("Incomplete RGB export")
        for path in paths:
            with Image.open(path) as img:
                if img.size != (row["width"], row["height"]) or img.mode != "RGB":
                    raise ValueError("Unexpected RGB shape/mode")
        videos.append(VideoInput(key, paths, row["height"], row["width"]))
        selected.append(row)
    return videos, selected, data


def load_ground_truth(folder, record):
    """Visible GT only; stable identity = channel+1, never chosen per frame."""
    frames = [[] for _ in range(record["frames"])]
    for channel in record["channels"]:
        if channel["category"] not in CLASSES:
            continue
        for t in range(record["frames"]):
            path = (
                Path(folder)
                / str(record["id"])
                / f'mask-{channel["index"]}'
                / f"{t:05d}.png"
            )
            rgba = np.asarray(Image.open(path))
            if rgba.shape != (record["height"], record["width"], 4):
                raise ValueError("GT dimensions differ")
            mask = rgba[..., 3] > 0
            if int(mask.sum()) != channel["areas"][t]:
                raise ValueError("GT area differs from audit")
            if mask.any():
                frames[t].append(
                    Instance(
                        channel["index"] + 1, channel["category"], mask_box(mask), mask
                    )
                )
    return frames


def input_provenance(videos, records, source):
    """Fingerprint every actual RGB and GT input, not just a directory name."""
    files = []
    for video, row in zip(videos, records):
        for path in video.rgb_paths:
            files.append(
                {"file": f"{video.video_id}/rgb/{path.name}", "sha256": digest(path)}
            )
        base = video.rgb_paths[0].parent.parent
        for channel in row["channels"]:
            if channel["category"] not in CLASSES:
                continue
            for t in range(row["frames"]):
                path = base / f'mask-{channel["index"]}' / f"{t:05d}.png"
                files.append(
                    {
                        "file": f'{video.video_id}/mask-{channel["index"]}/{path.name}',
                        "sha256": digest(path),
                    }
                )
    return {
        "source_archive": source["source_name"],
        "source_archive_sha256": source["source_sha256"],
        "videos": records,
        "files": files,
        "role": "development_pilot_only",
        "timing": "exported steps; original timestamps/FPS unavailable",
        "exclusion_rule": "Exclude these pilot videos from the future held-out evaluation split.",
    }
