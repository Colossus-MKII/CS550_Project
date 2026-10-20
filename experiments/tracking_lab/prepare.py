"""Export a small, lossless teaching preview from the audited local dataset.

Only explicitly selected samples are decoded. RGB PNGs preserve original array
pixels; white/transparent mask PNGs represent mask > 0. Categorical values,
instance channels, areas and provenance remain in the manifest.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile
import zipfile

import numpy as np
from PIL import Image

from . import ROOT

DEFAULT_SOURCE = ROOT / "data/raw/youtube_vis_2021_slotcurri"
DEFAULT_SAMPLES = (
    (2686, "person"),
    (2744, "dog"),
    (2689, "cat"),
    (2718, "horse"),
    (2692, "car"),
)
PALETTE = (
    (25, 207, 120),
    (255, 158, 30),
    (55, 145, 245),
    (219, 78, 200),
    (245, 210, 45),
    (80, 207, 220),
    (241, 100, 90),
    (156, 120, 240),
)


def export_sample(video, masks, record, destination, focus):
    """Write view-only assets; never alter categorical arrays or source records."""
    if video.dtype != np.uint8 or video.ndim != 4 or video.shape[-1] != 3:
        raise ValueError("Expected a uint8 RGB sequence")
    if masks.ndim != 4 or masks.shape[:3] != video.shape[:3]:
        raise ValueError("Video and mask dimensions must agree")
    if record.get("errors"):
        raise ValueError("Samples with audit errors cannot enter the viewer")
    key = str(record["video_id"])
    folder = destination / key
    (folder / "rgb").mkdir(parents=True, exist_ok=True)
    channels = []
    by_channel = {t["channel"]: t for t in record["tracks"]}
    for channel in range(masks.shape[-1]):
        track = by_channel.get(channel)
        if track is None:
            raise ValueError(f"Sample {key} channel {channel} has no audited category")
        values = masks[..., channel]
        if np.any((values != 0) & (values != track["category_id"])):
            raise ValueError("Categorical channel is inconsistent with the audit")
        areas = np.count_nonzero(values, axis=(1, 2)).tolist()
        if areas != track["areas"]:
            raise ValueError("Foreground areas differ from the audited arrays")
        color = PALETTE[channel % len(PALETTE)]
        channels.append(
            {
                "index": channel,
                "category_id": track["category_id"],
                "category": track["category"],
                "color": list(color),
                "areas": areas,
            }
        )
        (folder / f"mask-{channel}").mkdir(exist_ok=True)
    for index, frame in enumerate(video):
        Image.fromarray(frame).save(
            folder / "rgb" / f"{index:05d}.png", compress_level=3
        )
        for channel in range(masks.shape[-1]):
            alpha = (masks[index, ..., channel] > 0).astype(np.uint8) * 255
            rgba = np.full((*alpha.shape, 4), 255, dtype=np.uint8)
            rgba[..., 3] = alpha
            Image.fromarray(rgba).save(
                folder / f"mask-{channel}" / f"{index:05d}.png", compress_level=3
            )
    poster = Image.fromarray(video[0]).convert("RGBA")
    for channel, item in enumerate(channels):
        layer = np.zeros((*masks.shape[1:3], 4), dtype=np.uint8)
        layer[..., :3] = item["color"]
        layer[..., 3] = (masks[0, ..., channel] > 0).astype(np.uint8) * 135
        poster = Image.alpha_composite(poster, Image.fromarray(layer))
    poster.convert("RGB").save(folder / "poster.png", compress_level=3)
    return {
        "id": int(key),
        "focus": focus,
        "frames": len(video),
        "width": video.shape[2],
        "height": video.shape[1],
        "video_shape": list(video.shape),
        "mask_shape": list(masks.shape),
        "channels": channels,
        "source_shard": record["shard"],
        "source_video_key": key,
        "source_dtype": str(video.dtype),
    }


def prepare(archive_path, audit_path, destination, selection=DEFAULT_SAMPLES):
    archive_path, audit_path, destination = map(
        Path, (archive_path, audit_path, destination)
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if archive_path.stat().st_size != audit["archive_bytes"] or audit["partial_audit"]:
        raise ValueError("A complete audited archive is required")
    records = {s["video_id"]: s for shard in audit["shards"] for s in shard["samples"]}
    requested = dict(selection)
    missing = set(requested) - set(records)
    if missing:
        raise ValueError(f"Selected samples are missing: {sorted(missing)}")
    shards = sorted({records[key]["shard"] for key in requested})
    inventory = {entry["name"]: entry for entry in audit["inventory"]}
    destination.mkdir(parents=True, exist_ok=True)
    exported = {}
    with zipfile.ZipFile(archive_path) as outer:
        for shard in shards:
            info = outer.getinfo(shard)
            expected = inventory[shard]
            if (
                info.file_size != expected["bytes"]
                or f"{info.CRC:08x}" != expected["crc32"]
            ):
                raise ValueError("Source shard differs from the audited inventory")
            arrays = {}
            with outer.open(shard) as zipped, tarfile.open(
                fileobj=zipped, mode="r|"
            ) as inner:
                for member in inner:
                    if not member.isfile():
                        continue
                    name = Path(member.name).name
                    parts = name.split(".")
                    if len(parts) != 3 or not parts[0].isdigit():
                        continue
                    key = int(parts[0])
                    if key not in requested or parts[1] not in (
                        "video",
                        "segmentations",
                    ):
                        continue
                    if member.size > 512 * 1024 * 1024:
                        raise ValueError(
                            "Selected array exceeds the preview memory budget"
                        )
                    with inner.extractfile(member) as stream:
                        array = np.load(io.BytesIO(stream.read()), allow_pickle=False)
                    pair = arrays.setdefault(key, {})
                    pair[parts[1]] = array
                    if set(pair) == {"video", "segmentations"}:
                        exported[key] = export_sample(
                            pair["video"],
                            pair["segmentations"],
                            records[key],
                            destination,
                            requested[key],
                        )
                        del arrays[key]
                        print(
                            f'Exported sample {key}: {exported[key]["frames"]} frames',
                            flush=True,
                        )
                while zipped.read(8 * 1024 * 1024):
                    pass
    if set(exported) != set(requested):
        raise ValueError("Not every selected sample had both arrays")
    summary = audit["summary"]
    result = {
        "schema": 1,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": archive_path.name,
        "source_bytes": audit["archive_bytes"],
        "source_sha256": audit["archive_sha256"],
        "audit": {
            key: summary[key]
            for key in (
                "video_count",
                "annotated_video_count",
                "video_only_count",
                "target_union_video_count",
                "zip_shards_crc_verified",
                "labeled_frame_count",
                "short_side_values",
                "labeled_sequence_length_range",
            )
        },
        "target_counts": {
            category: {"videos": v["videos"], "tracks": v["tracks"]}
            for category, v in summary["target_counts"].items()
        },
        "samples": [exported[key] for key, _ in selection],
        "preview_encoding": {
            "rgb": "lossless RGB PNG",
            "mask": "white foreground / transparent background; source array > 0",
            "instance_identity": "source video ID plus instance-channel index",
            "original_timestamps_available": False,
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=DEFAULT_SOURCE / "ytvis2021_resized.zip"
    )
    parser.add_argument(
        "--audit", type=Path, default=DEFAULT_SOURCE / "audit/audit.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = prepare(args.archive, args.audit, args.output)
    print(
        f'Ready: {len(manifest["samples"])} samples, {sum(s["frames"] for s in manifest["samples"])} frames'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
