#!/usr/bin/env python3
"""Select and split a reproducible five-category YouTube-VIS 2021 subset."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


TARGET_CATEGORIES = ("person", "dog", "cat", "horse", "car")
SPLITS = (("train", 0.60), ("validation", 0.20), ("evaluation", 0.20))


def video_categories(dataset: dict) -> tuple[dict[int, set[str]], dict[int, dict]]:
    category_names = {
        int(category["id"]): str(category["name"]).strip().lower()
        for category in dataset["categories"]
    }
    target_ids = {
        category_id: name
        for category_id, name in category_names.items()
        if name in TARGET_CATEGORIES
    }
    missing = sorted(set(TARGET_CATEGORIES) - set(target_ids.values()))
    if missing:
        raise ValueError(f"Missing target categories in annotations: {missing}")

    categories_by_video: dict[int, set[str]] = defaultdict(set)
    for annotation in dataset["annotations"]:
        category_id = int(annotation["category_id"])
        if category_id in target_ids:
            categories_by_video[int(annotation["video_id"])].add(target_ids[category_id])

    videos = {int(video["id"]): video for video in dataset["videos"]}
    return categories_by_video, videos


def balanced_selection(
    categories_by_video: dict[int, set[str]], max_videos: int, rng: random.Random
) -> list[int]:
    pools = {
        category: [
            video_id
            for video_id, categories in categories_by_video.items()
            if category in categories
        ]
        for category in TARGET_CATEGORIES
    }
    for pool in pools.values():
        rng.shuffle(pool)

    selected: list[int] = []
    selected_set: set[int] = set()
    cursors = Counter()
    while len(selected) < max_videos:
        progress = False
        for category in TARGET_CATEGORIES:
            pool = pools[category]
            while cursors[category] < len(pool) and pool[cursors[category]] in selected_set:
                cursors[category] += 1
            if cursors[category] >= len(pool):
                continue
            video_id = pool[cursors[category]]
            cursors[category] += 1
            selected.append(video_id)
            selected_set.add(video_id)
            progress = True
            if len(selected) >= max_videos:
                break
        if not progress:
            break

    remaining = [video_id for video_id in categories_by_video if video_id not in selected_set]
    rng.shuffle(remaining)
    selected.extend(remaining[: max_videos - len(selected)])
    return selected


def assign_splits(
    video_ids: list[int], categories_by_video: dict[int, set[str]], rng: random.Random
) -> dict[str, list[int]]:
    rng.shuffle(video_ids)
    total = len(video_ids)
    targets = {
        "train": round(total * 0.60),
        "validation": round(total * 0.20),
    }
    targets["evaluation"] = total - targets["train"] - targets["validation"]

    assignments = {name: [] for name, _ in SPLITS}
    counts = {name: Counter() for name, _ in SPLITS}
    global_counts = Counter(
        category
        for video_id in video_ids
        for category in categories_by_video[video_id]
    )

    ordered = sorted(
        video_ids,
        key=lambda video_id: (
            min(global_counts[category] for category in categories_by_video[video_id]),
            -len(categories_by_video[video_id]),
            video_id,
        ),
    )

    ratios = dict(SPLITS)
    for video_id in ordered:
        categories = categories_by_video[video_id]
        available = [name for name, _ in SPLITS if len(assignments[name]) < targets[name]]
        if not available:
            raise RuntimeError("No split has remaining capacity")

        def deficit(split: str) -> tuple[float, float, int]:
            category_deficit = sum(
                global_counts[category] * ratios[split] - counts[split][category]
                for category in categories
            )
            size_deficit = targets[split] - len(assignments[split])
            return category_deficit, size_deficit / max(targets[split], 1), -len(assignments[split])

        destination = max(available, key=deficit)
        assignments[destination].append(video_id)
        counts[destination].update(categories)

    return assignments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-videos", type=int, default=200)
    parser.add_argument("--seed", type=int, default=550)
    args = parser.parse_args()

    if args.max_videos <= 0:
        parser.error("--max-videos must be positive")

    dataset = json.loads(args.annotations.read_text(encoding="utf-8"))
    categories_by_video, videos = video_categories(dataset)
    rng = random.Random(args.seed)
    selected = balanced_selection(categories_by_video, args.max_videos, rng)
    assignments = assign_splits(selected, categories_by_video, rng)

    output = {
        "source": str(args.annotations),
        "seed": args.seed,
        "target_categories": list(TARGET_CATEGORIES),
        "requested_max_videos": args.max_videos,
        "selected_video_count": len(selected),
        "splits": {},
    }
    for split, video_ids in assignments.items():
        output["splits"][split] = [
            {
                "video_id": video_id,
                "categories": sorted(categories_by_video[video_id]),
                "file_names": videos[video_id].get("file_names", []),
                "width": videos[video_id].get("width"),
                "height": videos[video_id].get("height"),
                "length": videos[video_id].get("length"),
            }
            for video_id in sorted(video_ids)
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.output} with {len(selected)} videos")
    for split, entries in output["splits"].items():
        counts = Counter(category for entry in entries for category in entry["categories"])
        summary = ", ".join(f"{category}={counts[category]}" for category in TARGET_CATEGORIES)
        print(f"{split}: {len(entries)} videos ({summary})")


if __name__ == "__main__":
    main()
