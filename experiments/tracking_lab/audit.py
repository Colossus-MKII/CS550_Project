"""Audit SlotCurri's downloaded YTVIS archive without extracting all tar shards.

Read NPY headers and every mask, check paired shapes and category consistency,
and consume every ZIP member to validate its CRC. Never load pickled arrays.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import zipfile

import numpy as np
import requests


TARGETS = ("person", "dog", "cat", "horse", "car")
META_URL = (
    "https://raw.githubusercontent.com/facebookresearch/Mask2Former/main/"
    "mask2former_video/data_video/datasets/ytvis.py"
)
SOURCE_URL = "https://drive.google.com/file/d/1Iv-2zK6MnH0oDFTx9iBgQcPNh5PBzM7i/view"
PREPARATION_URL = (
    "https://raw.githubusercontent.com/wjun0830/SlotCurri/main/data/save_ytvis2021.py"
)
ARCHIVE_BYTES = 28377138264
CONTENT_URL = (
    "https://drive.usercontent.google.com/download?"
    "id=1Iv-2zK6MnH0oDFTx9iBgQcPNh5PBzM7i&export=download&confirm=t"
)
TAIL = None


class GrowingArchive(io.RawIOBase):
    """Read already-downloaded bytes, using only a cached remote ZIP directory.

    This overlaps local CRC/header checks with the ongoing sequential download.
    No payload is downloaded twice. Wait for a requested payload to reach disk.
    """

    def __init__(self, path):
        self.path, self.position = Path(path), 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = (
            offset
            if whence == 0
            else (self.position + offset if whence == 1 else ARCHIVE_BYTES + offset)
        )
        return self.position

    def read(self, size=-1):
        size = min(
            size if size >= 0 else ARCHIVE_BYTES - self.position,
            ARCHIVE_BYTES - self.position,
        )
        if size <= 0:
            return b""
        tail_start = ARCHIVE_BYTES - len(TAIL)
        if self.position >= tail_start:
            data = TAIL[self.position - tail_start : self.position - tail_start + size]
        else:
            deadline = time.monotonic() + 600
            while True:
                path = self.path if self.path.exists() else self.path.with_suffix("")
                try:
                    if path.stat().st_size >= self.position + size:
                        with path.open("rb") as stream:
                            stream.seek(self.position)
                            data = stream.read(size)
                        if len(data) == size:
                            break
                except FileNotFoundError:
                    pass  # The downloader may rename .part to .zip between calls.
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        "Download made insufficient progress for the next ZIP read"
                    )
                time.sleep(0.25)
        self.position += len(data)
        return data


def open_archive(path):
    return zipfile.ZipFile(
        GrowingArchive(path) if str(path).endswith(".part") else path
    )


def category_metadata():
    response = requests.get(META_URL, timeout=(30, 90))
    response.raise_for_status()
    tree = ast.parse(response.text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "YTVIS_CATEGORIES_2021"
            for target in node.targets
        ):
            categories = ast.literal_eval(node.value)
            return {int(c["id"]): str(c["name"]) for c in categories}, sha256(
                response.content
            ).hexdigest()
    raise ValueError("Could not locate the explicit YTVIS 2021 category metadata")


def read_header(stream, member_size):
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
    elif version == (2, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream)
    else:
        raise ValueError(f"Unexpected NPY version: {version}")
    if dtype.hasobject:
        raise ValueError("Object/pickled arrays are not accepted")
    size = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
    if stream.tell() + size != member_size:
        raise ValueError(f"NPY payload size mismatch: {shape}, {dtype}, {member_size}")
    return {"shape": list(shape), "dtype": str(dtype), "fortran": fortran}, dtype, size


def inspect_masks(mask, categories):
    errors, warnings, tracks = [], [], []
    if mask.ndim != 4 or mask.dtype.kind not in "uif":
        return [], [f"Unexpected mask array: {mask.shape}, {mask.dtype}"], [], []
    all_foreground = np.zeros(mask.shape[:1], dtype=bool)
    for channel in range(mask.shape[3]):
        values = mask[..., channel]
        if mask.dtype.kind == "f" and not np.isfinite(values).all():
            errors.append(f"Channel {channel} contains non-finite labels")
            continue
        label_value = float(values.max())
        if label_value == 0:
            warnings.append(f"Channel {channel} has no foreground in any frame")
            continue
        label = int(label_value)
        if label_value != label or label not in categories:
            errors.append(
                f"Channel {channel} has unsupported category value {label_value}"
            )
            continue
        areas = np.count_nonzero(values, axis=(1, 2))
        expected = np.count_nonzero(values == label, axis=(1, 2))
        if not np.array_equal(areas, expected):
            errors.append(
                f"Channel {channel} has nonzero values from multiple categories"
            )
        visible = np.flatnonzero(areas)
        if not len(visible):
            continue
        all_foreground |= areas > 0
        gaps = np.diff(visible)
        tracks.append(
            {
                "channel": channel,
                "category_id": label,
                "category": categories[label],
                "visible_frames": visible.tolist(),
                "areas": areas.tolist(),
                "first_visible_index": int(visible[0]),
                "last_visible_index": int(visible[-1]),
                "visible_frame_count": int(len(visible)),
                "max_visibility_gap_in_exported_steps": (
                    int(gaps.max() - 1) if len(gaps) else 0
                ),
            }
        )
    return tracks, errors, warnings, np.flatnonzero(~all_foreground).tolist()


def inspect_shard(archive, name, categories):
    samples, errors, unknown = {}, [], []
    split = "validation" if "ytvis-validation-" in name else "train"
    with open_archive(archive) as outer:
        info = outer.getinfo(name)
        with outer.open(name) as zipped:
            with tarfile.open(fileobj=zipped, mode="r|", bufsize=1024 * 1024) as inner:
                for member in inner:
                    if not member.isfile():
                        continue
                    match = re.fullmatch(
                        r"(\d+)\.(.+)\.npy", PurePosixPath(member.name).name
                    )
                    if match is None:
                        unknown.append(member.name)
                        continue
                    key, feature = match.groups()
                    sample = samples.setdefault(
                        key,
                        {
                            "video_id": int(key),
                            "shard": name,
                            "source_split": split,
                            "features": {},
                            "tracks": [],
                            "errors": [],
                            "warnings": [],
                        },
                    )
                    if feature in sample["features"]:
                        sample["errors"].append(f"Duplicate feature: {feature}")
                    stream = inner.extractfile(member)
                    try:
                        header, dtype, payload = read_header(stream, member.size)
                        sample["features"][feature] = header
                        if feature == "segmentations":
                            raw = stream.read(payload)
                            if len(raw) != payload:
                                raise ValueError("Truncated segmentation payload")
                            mask = np.frombuffer(raw, dtype=dtype).reshape(
                                header["shape"], order="F" if header["fortran"] else "C"
                            )
                            tracks, mask_errors, warnings, empty = inspect_masks(
                                mask, categories
                            )
                            sample["tracks"] = tracks
                            sample["errors"].extend(mask_errors)
                            sample["warnings"].extend(warnings)
                            sample["all_instances_empty_frame_indices"] = empty
                            del mask, raw
                    except Exception as error:
                        sample["errors"].append(
                            f"{feature}: {type(error).__name__}: {error}"
                        )
                    finally:
                        stream.close()
            # Consume padding and any trailing bytes so ZIP CRC is actually checked.
            while zipped.read(8 * 1024 * 1024):
                pass
    for sample in samples.values():
        video = sample["features"].get("video")
        masks = sample["features"].get("segmentations")
        if video is None:
            sample["errors"].append("Missing video.npy")
        elif (
            len(video["shape"]) != 4
            or video["shape"][-1] != 3
            or video["dtype"] != "uint8"
        ):
            sample["errors"].append(f"Unexpected video shape/dtype: {video}")
        if masks and video and masks["shape"][:3] != video["shape"][:3]:
            sample["errors"].append(
                "Video and segmentation frame/spatial shapes differ"
            )
        sample["categories"] = sorted({track["category"] for track in sample["tracks"]})
        sample["target_categories"] = sorted(set(sample["categories"]) & set(TARGETS))
        sample["annotated"] = masks is not None
    return {
        "name": name,
        "split": split,
        "bytes": info.file_size,
        "compressed_bytes": info.compress_size,
        "zip_crc32": f"{info.CRC:08x}",
        "zip_crc_verified": True,
        "samples": list(samples.values()),
        "errors": errors,
        "unknown_members": unknown,
    }


def summarize(shards):
    samples = [sample for shard in shards for sample in shard["samples"]]
    seen, duplicates = set(), []
    for sample in samples:
        key = sample["video_id"]
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    labeled = [s for s in samples if s["annotated"]]
    usable = [s for s in labeled if not s["errors"]]
    eligible = [s for s in usable if s["target_categories"]]
    category_counts = {}
    for category in TARGETS:
        videos = [s for s in usable if category in s["categories"]]
        tracks = [t for s in videos for t in s["tracks"] if t["category"] == category]
        category_counts[category] = {
            "videos": len(videos),
            "tracks": len(tracks),
            "visible_instance_frames": sum(t["visible_frame_count"] for t in tracks),
            "video_ids": sorted(s["video_id"] for s in videos),
        }
    all_categories = Counter(t["category"] for s in usable for t in s["tracks"])
    errors = [
        dict(video_id=s["video_id"], shard=s["shard"], errors=s["errors"])
        for s in samples
        if s["errors"]
    ]
    return {
        "zip_shards": len(shards),
        "zip_shards_crc_verified": sum(s["zip_crc_verified"] for s in shards),
        "split_video_counts": dict(Counter(s["source_split"] for s in samples)),
        "video_count": len(samples),
        "unique_video_ids": len(seen),
        "duplicate_video_ids": duplicates,
        "annotated_video_count": len(labeled),
        "structurally_valid_annotated_video_count": len(usable),
        "video_only_count": sum(not s["annotated"] for s in samples),
        "labeled_frame_count": sum(s["features"]["video"]["shape"][0] for s in usable),
        "error_video_count": len(errors),
        "errors": errors,
        "warning_video_count": sum(bool(s["warnings"]) for s in samples),
        "all_category_track_counts": dict(sorted(all_categories.items())),
        "target_counts": category_counts,
        "target_union_video_count": len(eligible),
        "target_union_video_ids": sorted(s["video_id"] for s in eligible),
        "supports_five_categories": all(
            category_counts[c]["videos"] > 0 for c in TARGETS
        ),
        "supports_requested_200_target_videos": len(eligible) >= 200 and not duplicates,
        "short_side_values": sorted(
            {min(s["features"]["video"]["shape"][1:3]) for s in usable}
        ),
        "labeled_sequence_length_range": [
            min((s["features"]["video"]["shape"][0] for s in usable), default=0),
            max((s["features"]["video"]["shape"][0] for s in usable), default=0),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--shard-limit", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    categories, metadata_hash = category_metadata()
    if str(args.archive).endswith(".part"):
        global TAIL
        response = requests.get(
            CONTENT_URL,
            headers={"Range": f"bytes={ARCHIVE_BYTES-65536}-"},
            timeout=(30, 90),
        )
        response.raise_for_status()
        if response.status_code != 206 or len(response.content) != 65536:
            raise ValueError(
                "Unable to read the remote ZIP directory with a byte range"
            )
        TAIL = response.content
    with open_archive(args.archive) as archive:
        infos = archive.infolist()
        inventory = [
            {
                "name": i.filename,
                "bytes": i.file_size,
                "compressed_bytes": i.compress_size,
                "crc32": f"{i.CRC:08x}",
            }
            for i in infos
        ]
        names = [i.filename for i in infos if i.filename.endswith(".tar")]
    # Annotated data first so category coverage is available before the full scan ends.
    names.sort(
        key=lambda name: (
            (
                "validation" in name
                if str(args.archive).endswith(".part")
                else "validation" not in name
            ),
            name,
        )
    )
    if args.shard_limit:
        names = names[: args.shard_limit]
    shards = []
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(inspect_shard, args.archive, name, categories): name
            for name in names
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
            except Exception as error:
                raise RuntimeError(f"Shard integrity/audit failed: {name}") from error
            shards.append(result)
            checkpoint = {
                "completed_shards": len(shards),
                "total_shards": len(names),
                "elapsed_seconds": round(time.monotonic() - start, 1),
                "summary": summarize(shards),
            }
            (args.output / "progress.json").write_text(
                json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "completed_shards": len(shards),
                        "total_shards": len(names),
                        "shard": name,
                        "samples": len(result["samples"]),
                        "target_union_so_far": checkpoint["summary"][
                            "target_union_video_count"
                        ],
                        "seconds": checkpoint["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
    if str(args.archive).endswith(".part"):
        while True:
            completed = args.archive.with_suffix("")
            path = args.archive if args.archive.exists() else completed
            if path.exists() and path.stat().st_size == ARCHIVE_BYTES:
                args.archive = path
                break
            time.sleep(0.25)
    digest = sha256()
    with args.archive.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL,
        "archive": str(args.archive.resolve()),
        "archive_bytes": args.archive.stat().st_size,
        "archive_sha256": digest.hexdigest(),
        "partial_audit": bool(args.shard_limit),
        "category_metadata_source": META_URL,
        "category_metadata_sha256": metadata_hash,
        "category_map": categories,
        "preparation_source": PREPARATION_URL,
        "limitations": [
            "CRC validates downloaded bytes against the ZIP directory, not an upstream published cryptographic checksum.",
            "Checks establish export consistency, not completeness against the missing original annotation JSON.",
            "Instance channel indices are the exported within-video identities; original annotation IDs are absent.",
            "Original image filenames, source timestamps/FPS and source clip identities are not embedded in NPY headers.",
            "Video array frame order follows the exporter; exact original timestamps and source grouping require original metadata.",
            "Empty masks may represent absence; the audit does not treat them as missing annotations automatically.",
            "No model predictions or recovery events were used to select candidate videos.",
        ],
        "inventory": inventory,
        "summary": summarize(shards),
        "shards": sorted(shards, key=lambda s: s["name"]),
    }
    path = args.output / "audit.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    lines = [
        "SlotCurri YouTube-VIS 2021 archive audit",
        f'Created UTC: {report["created_utc"]}',
        f'Archive: {report["archive"]}',
        f'Archive bytes: {report["archive_bytes"]:,}',
        f'SHA-256: {report["archive_sha256"]}',
        f'Partial audit: {report["partial_audit"]}',
        f'TAR shards CRC checked: {summary["zip_shards_crc_verified"]}',
        f'Unique video IDs: {summary["unique_video_ids"]}',
        f'Videos with mask arrays: {summary["annotated_video_count"]}',
        f'Structurally valid annotated videos: {summary["structurally_valid_annotated_video_count"]}',
        f'Video-only samples: {summary["video_only_count"]}',
        f'Videos with errors: {summary["error_video_count"]}',
        "",
        "Target category | usable videos | instance tracks | visible instance-frames",
    ]
    for category in TARGETS:
        count = summary["target_counts"][category]
        lines.append(
            f'{category} | {count["videos"]} | {count["tracks"]} | {count["visible_instance_frames"]}'
        )
    lines.extend(
        [
            "",
            f'UNIQUE videos containing any target category: {summary["target_union_video_count"]}',
            f'Supports 200 target-category videos: {summary["supports_requested_200_target_videos"]}',
            "Videos containing multiple categories are counted only once in this union.",
            "",
            "Limits of this check:",
            *["- " + value for value in report["limitations"]],
        ]
    )
    (args.output / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "FINAL",
        json.dumps(
            {
                "report": str(path.resolve()),
                "annotated_videos": summary["annotated_video_count"],
                "target_videos": summary["target_union_video_count"],
                "target_category_video_counts": {
                    c: summary["target_counts"][c]["videos"] for c in TARGETS
                },
                "supports_200": summary["supports_requested_200_target_videos"],
                "error_videos": summary["error_video_count"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
