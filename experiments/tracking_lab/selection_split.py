"""Data-only, versioned split preparation. NO detector, SAM or H/R imports.

fingerprint(): hash all 226 RGB sequences, retain only sparse image fingerprints.
freeze_split(): seeded group assignment with exact sizes and class coverage.
No held-out images/predictions are rendered. A source URL grouping is unavailable;
exact/strong visual duplicate components are the available conservative proxy.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import random
import tarfile
import zipfile

import numpy as np

from .common import CLASSES, digest, write_json

OLD_VIDEOS = (2686, 2744, 2689, 2718, 2692)
SIZES = {"development": 120, "validation": 40, "evaluation": 40, "excluded": 26}
QUOTAS = {"dog": (10, 3, 4), "cat": (3, 1, 2), "horse": (7, 2, 3), "car": (20, 6, 7)}


def audit_records(path):
    audit = json.loads(Path(path).read_text(encoding="utf-8"))
    if audit["partial_audit"]:
        raise ValueError("Full audit required")
    records = sorted(
        (
            v
            for s in audit["shards"]
            for v in s["samples"]
            if v["annotated"] and v["target_categories"] and not v["errors"]
        ),
        key=lambda v: v["video_id"],
    )
    if len(records) != 226 or len({v["video_id"] for v in records}) != 226:
        raise ValueError(
            "Unexpected target inventory; review constraints before splitting"
        )
    return audit, records


def image_fingerprint(rgb):
    import cv2

    gray = cv2.cvtColor(
        cv2.resize(rgb, (32, 32), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY
    ).astype(np.float32)
    block = cv2.dct(gray)[:8, :8].flatten()[1:]
    bits = block > np.median(block)
    value = sum(int(bit) << i for i, bit in enumerate(bits))
    return {"phash": f"{value:016x}", "mean_rgb": rgb.mean(axis=(0, 1)).tolist()}


def strong_duplicate(a, b):
    if a["rgb_sha256"] == b["rgb_sha256"]:
        return "exact_rgb"
    if abs(a["width"] / a["height"] - b["width"] / b["height"]) > 0.03:
        return None
    candidates = []
    for i, x in enumerate(a["images"]):
        for j, y in enumerate(b["images"]):
            distance = (int(x["phash"], 16) ^ int(y["phash"], 16)).bit_count()
            color = np.linalg.norm(np.asarray(x["mean_rgb"]) - y["mean_rgb"])
            if distance <= 6 and color < 15:
                candidates.append((i, j))
    if any(i != k and j != l for i, j in candidates for k, l in candidates):
        return "two_sparse_frames_phash_le6_color_l2_lt15"
    return None


def fingerprint(archive, audit_path, output):
    archive, audit_path, output = map(Path, (archive, audit_path, output))
    if output.exists():
        raise FileExistsError("Fingerprint output must be new")
    audit, records = audit_records(audit_path)
    if archive.stat().st_size != audit["archive_bytes"]:
        raise ValueError("Archive size differs from full audit")
    requested = {v["video_id"]: v for v in records}
    inventory = {r["name"]: r for r in audit["inventory"]}
    fingerprints = []
    with zipfile.ZipFile(archive) as outer:
        for shard in sorted({r["shard"] for r in records}):
            info = outer.getinfo(shard)
            if (info.file_size, f"{info.CRC:08x}") != (
                inventory[shard]["bytes"],
                inventory[shard]["crc32"],
            ):
                raise ValueError("Audited shard changed")
            with outer.open(shard) as zipped, tarfile.open(
                fileobj=zipped, mode="r|"
            ) as inner:
                for member in inner:
                    parts = Path(member.name).name.split(".")
                    if (
                        len(parts) != 3
                        or not parts[0].isdigit()
                        or parts[1:] != ["video", "npy"]
                    ):
                        continue
                    identity = int(parts[0])
                    if identity not in requested:
                        continue
                    with inner.extractfile(member) as stream:
                        video = np.load(io.BytesIO(stream.read()), allow_pickle=False)
                    record = requested[identity]
                    if (
                        list(video.shape) != record["features"]["video"]["shape"]
                        or video.dtype != np.uint8
                    ):
                        raise ValueError("RGB shape/dtype differs")
                    indices = sorted(set([0, len(video) // 2, len(video) - 1]))
                    fingerprints.append(
                        {
                            "video_id": identity,
                            "frames": len(video),
                            "height": video.shape[1],
                            "width": video.shape[2],
                            "rgb_sha256": sha256(video.tobytes()).hexdigest(),
                            "images": [
                                {"frame": i, **image_fingerprint(video[i])}
                                for i in indices
                            ],
                        }
                    )
                    del video
            print("Fingerprint shard", shard, "videos", len(fingerprints), flush=True)
    fingerprints.sort(key=lambda r: r["video_id"])
    if len(fingerprints) != 226:
        raise ValueError("Incomplete fingerprint pass")
    parent = {r["video_id"]: r["video_id"] for r in fingerprints}

    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    pairs = []
    for i, a in enumerate(fingerprints):
        for b in fingerprints[i + 1 :]:
            reason = strong_duplicate(a, b)
            if reason:
                x, y = root(a["video_id"]), root(b["video_id"])
                parent[max(x, y)] = min(x, y)
                pairs.append({"a": a["video_id"], "b": b["video_id"], "reason": reason})
    groups = {}
    for v in parent:
        groups.setdefault(str(root(v)), []).append(v)
    result = {
        "schema": 1,
        "role": "data_only_duplicate_screen_no_predictions_or_human_heldout_preview",
        "audit_sha256": digest(audit_path),
        "archive_sha256": audit["archive_sha256"],
        "fingerprints": fingerprints,
        "groups": [
            {"group_id": "visual-" + key, "video_ids": values}
            for key, values in sorted(groups.items())
        ],
        "duplicate_pairs": pairs,
        "limitations": [
            "Sparse perceptual hashes cannot prove source-video independence.",
            "No original source URLs are included in the export; new obvious near duplicates must be quarantined, not moved across frozen splits.",
        ],
    }
    write_json(output, result)
    print(
        "Fingerprint complete",
        len(groups),
        "groups;",
        len(pairs),
        "strong duplicate pairs",
        flush=True,
    )


def freeze_split(audit_path, fingerprints_path, output):
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import lil_matrix

    output = Path(output)
    if output.exists():
        raise FileExistsError("Frozen split must not be overwritten")
    audit, records = audit_records(audit_path)
    fingerprints = json.loads(Path(fingerprints_path).read_text(encoding="utf-8"))
    if fingerprints["audit_sha256"] != digest(audit_path):
        raise ValueError("Duplicate screen uses a different audit")
    by_id = {r["video_id"]: r for r in records}
    groups = fingerprints["groups"]
    if sorted(v for g in groups for v in g["video_ids"]) != sorted(by_id):
        raise ValueError("Invalid duplicate groups")
    names = list(SIZES)
    n = len(groups) * 4
    rows, lower, upper = [], [], []

    def constraint(values, lo, hi):
        rows.append(values)
        lower.append(lo)
        upper.append(hi)

    for i, g in enumerate(groups):
        constraint({i * 4 + j: 1 for j in range(4)}, 1, 1)
    for j, name in enumerate(names):
        constraint(
            {i * 4 + j: len(g["video_ids"]) for i, g in enumerate(groups)},
            SIZES[name],
            SIZES[name],
        )
    for i, g in enumerate(groups):
        if set(g["video_ids"]) & set(OLD_VIDEOS):
            constraint({i * 4: 1}, 1, 1)
    for category, targets in QUOTAS.items():
        for j, target in enumerate(targets):
            values = {
                i * 4
                + j: sum(
                    category in by_id[v]["target_categories"] for v in g["video_ids"]
                )
                for i, g in enumerate(groups)
            }
            constraint(values, target, target)
    for j, minimum in enumerate((38, 12, 12)):
        values = {
            i * 4
            + j: sum(
                by_id[v]["features"]["video"]["shape"][0] >= 41 for v in g["video_ids"]
            )
            for i, g in enumerate(groups)
        }
        constraint(values, minimum, np.inf)
    matrix = lil_matrix((len(rows), n))
    for i, row in enumerate(rows):
        for col, value in row.items():
            matrix[i, col] = value
    rng = random.Random(550)
    objective = np.array([rng.random() for _ in range(n)])
    solution = milp(
        objective,
        integrality=np.ones(n),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(matrix.tocsr(), lower, upper),
        options={"time_limit": 60, "mip_rel_gap": 0},
    )
    if not solution.success:
        raise RuntimeError(
            "Coverage/group constraints infeasible; do not silently relax: "
            + solution.message
        )
    assignment = {name: [] for name in names}
    for i, g in enumerate(groups):
        values = solution.x[i * 4 : i * 4 + 4]
        if sum(values > 0.5) != 1:
            raise AssertionError("Nonbinary assignment")
        destination = names[int(np.argmax(values))]
        for v in g["video_ids"]:
            r = by_id[v]
            assignment[destination].append(
                {
                    "video_id": v,
                    "group_id": g["group_id"],
                    "categories": r["target_categories"],
                    "frames": r["features"]["video"]["shape"][0],
                }
            )
    for name in names:
        assignment[name].sort(key=lambda r: r["video_id"])
        assert len(assignment[name]) == SIZES[name]
    result = {
        "schema": 1,
        "version": "ytvis2021-200-seed550-v1",
        "status": "frozen_before_candidate_baseline_inference",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 550,
        "audit_sha256": digest(audit_path),
        "archive_sha256": audit["archive_sha256"],
        "duplicate_screen_sha256": digest(fingerprints_path),
        "old_development_videos": list(OLD_VIDEOS),
        "selected_video_count": 200,
        "splits": assignment,
        "policy": {
            "sizes": SIZES,
            "rare_class_exact_quotas_dev_val_eval": QUOTAS,
            "minimum_videos_with_41_steps_dev_val_eval": [38, 12, 12],
            "group_unit": "exact/strong sparse-frame visual-duplicate component",
            "solver": "scipy.optimize.milp; optimal seeded objective",
            "selection_information": "Only audited categories, lengths, old pilot membership and RGB duplicate fingerprints. No predictions or H/R outcomes.",
            "held_out_rule": "Do not render, score or inspect validation/evaluation predictions during candidate exploration.",
            "new_duplicate_rule": "Quarantine later-discovered related candidates; do not reshuffle held-out groups after seeing outcomes.",
        },
        "counts": {
            name: {
                "videos": len(values),
                "classes": dict(Counter(c for r in values for c in r["categories"])),
                "at_least_41_steps": sum(r["frames"] >= 41 for r in values),
            }
            for name, values in assignment.items()
        },
        "grouping_limitations": fingerprints["limitations"],
    }
    write_json(output, result)
    print(json.dumps(result["counts"], indent=2), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fingerprint", "split"))
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--fingerprints", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.action == "fingerprint":
        fingerprint(args.archive, args.audit, args.output)
    else:
        freeze_split(args.audit, args.fingerprints, args.output)


if __name__ == "__main__":
    main()
