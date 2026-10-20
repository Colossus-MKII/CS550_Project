"""Run ONLY frozen A0/B0 candidate baselines, one video per isolated archive.

Reuse tracking_lab.run.execute(), unchanged. There is NO H/R call, reset,
corrective GT prompt, training, server or network operation in this driver.
Per-video archives avoid losing all candidates if a crowded clip hits the
pre-existing 32-target SAM budget. Such exclusions are explicitly recorded.
"""

import argparse
from contextlib import redirect_stdout, redirect_stderr
import gc
import json
from pathlib import Path
import time
import traceback

from .common import digest, write_json


def execute(queue_path, split_path, data_root, output):
    from .run import execute as run_baseline, make_parser
    import torch

    queue_path, split_path, data_root, output = map(
        Path, (queue_path, split_path, data_root, output)
    )
    if output.exists():
        raise FileExistsError(
            "Keep all previous baseline runs; use a new cohort folder"
        )
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    development = {r["video_id"] for r in split["splits"]["development"]}
    if (
        queue["split_sha256"] != digest(split_path)
        or not set(queue["video_ids"]) <= development
    ):
        raise ValueError("Only frozen development candidates may be inferred")
    if queue["H_R_permitted"] is not False:
        raise ValueError("This driver is screening only")
    if not torch.cuda.is_available() or "3080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("This selection batch is restricted to the local RTX 3080")
    output.mkdir(parents=True)
    status = {
        "status": "running",
        "purpose": "automatic_baseline_screening_only_no_HR",
        "queue_sha256": digest(queue_path),
        "split_sha256": digest(split_path),
        "logical_device": "cuda:0",
        "videos": [],
        "H_R_runs": 0,
    }
    write_json(output / "cohort.json", status)
    started = time.perf_counter()
    for index, identity in enumerate(queue["video_ids"], 1):
        selection = output / "selections" / f"{identity}.json"
        write_json(
            selection,
            {
                "video_ids": [identity],
                "purpose": "frozen_development_candidate_baseline_only",
                "queue_sha256": digest(queue_path),
                "split_sha256": digest(split_path),
            },
        )
        destination = output / str(identity)
        args = make_parser().parse_args(
            [
                "--selection",
                str(selection),
                "--data-root",
                str(data_root),
                "--output",
                str(destination),
                "--device",
                "cuda:0",
            ]
        )
        print(
            "Baseline candidate",
            index,
            "/",
            len(queue["video_ids"]),
            identity,
            flush=True,
        )
        try:
            with (output / f"{identity}.log").open(
                "w", encoding="utf-8"
            ) as stream, redirect_stdout(stream), redirect_stderr(stream):
                run_baseline(args)
            summary = json.loads(
                (destination / "summary.json").read_text(encoding="utf-8")
            )
            if (
                summary["status"] != "inference_and_scoring_completed"
                or "3080" not in summary["environment"]["device"]
            ):
                raise AssertionError("Unexpected baseline completion/device")
            record = {
                "video_id": identity,
                "status": "baseline_completed",
                "folder": str(identity),
                "summary_sha256": digest(destination / "summary.json"),
                "device": summary["environment"]["device"],
            }
        except Exception as error:
            record = {
                "video_id": identity,
                "status": "failed",
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
            status["videos"].append(record)
            write_json(output / "cohort.json", status)
            if "target budget" not in str(error).lower():
                status["status"] = "failed_unexpected_error"
                write_json(output / "cohort.json", status)
                raise
        else:
            status["videos"].append(record)
        finally:
            gc.collect()
            torch.cuda.empty_cache()
        write_json(output / "cohort.json", status)
        print(identity, record["status"], flush=True)
    status["status"] = "baseline_screening_completed"
    status["wall_seconds"] = time.perf_counter() - started
    write_json(output / "cohort.json", status)
    print("Candidate baselines complete; H/R runs = 0", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queue", "split", "data-root", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    execute(args.queue, args.split, args.data_root, args.output)


if __name__ == "__main__":
    main()
