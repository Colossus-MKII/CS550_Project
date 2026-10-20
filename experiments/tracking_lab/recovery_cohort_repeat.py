"""Exact repeatability checks of two PRESELECTED difficult primary events.

E09 (small same-class competition) and E13 (cross-class occlusion) are fixed
before their main results are inspected. These 16 verification branches are
NOT new independent samples and are NOT pooled with the 128 primary branches.
No 2967, protocol changes, new conditions or repeat-by-winner selection.
"""

import argparse
from contextlib import redirect_stdout, redirect_stderr
import gc
import json
from pathlib import Path
import time

from .common import digest, load_predictions, write_json
from .recovery_cohort import read_json, INFERENCE_FILES
from .recovery_long_report import different_frames

REPEAT_EVENTS = ("E09", "E13")


def compare_verified(first, second, data_root):
    from .recovery_report import verify_recovery

    # The independent CPU renderer can finish a NEW primary run concurrently.
    # Its only numerical-metadata edit is the final summary status. Tolerate a
    # brief non-atomic JSON write, not a failed numerical check.
    def checked(path):
        for attempt in range(4):
            try:
                return verify_recovery(path, data_root)[0]
            except json.JSONDecodeError:
                if attempt == 3:
                    raise
                time.sleep(0.1)

    a, b = checked(first), checked(second)
    assert a["configuration"] == b["configuration"] and a["weights"] == b["weights"]
    for name in INFERENCE_FILES:
        assert a["source_sha256"][name] == b["source_sha256"][name], name
    left = {(r["condition"], r["group"]): r for r in a["branches"]}
    right = {(r["condition"], r["group"]): r for r in b["branches"]}
    assert left.keys() == right.keys() and len(left) == 8
    frames = 0
    for key, x in left.items():
        y = right[key]
        for field in ("prediction_id", "prefix_target_sha256", "correction"):
            assert x[field] == y[field]
        p, q = Path(first) / x["folder"], Path(second) / y["folder"]
        pp, qq = load_predictions(p), load_predictions(q)
        assert not different_frames(pp, qq), key
        assert read_json(p / "recovery.json") == read_json(q / "recovery.json"), key
        assert read_json(p / "state-trace.json") == read_json(
            q / "state-trace.json"
        ), key
        frames += len(pp)
    return {
        "status": "passed",
        "branches": 8,
        "frames_compared": frames,
        "comparison": "all IDs/classes/scores/boxes/binary masks, recovery curves and state/prompt/assignment traces exact",
        "first": str(Path(first).resolve()),
        "second": str(Path(second).resolve()),
        "independent_new_samples": 0,
    }


def execute(cohort, output):
    import torch
    from .recovery import execute as run_recovery, make_parser

    if not torch.cuda.is_available() or "3080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("Local RTX 3080 only")
    cohort, output = Path(cohort), Path(output)
    if output.exists():
        raise FileExistsError("Repeat verification uses a new output directory")
    plan = read_json(cohort / "cohort.json")
    if (
        plan["status"] not in {"inference_completed", "completed"}
        or plan["actual_branches"] != 128
    ):
        raise ValueError("Finish all primary inference before repeating")
    selected = [r for r in plan["events"] if r["event_id"] in REPEAT_EVENTS]
    assert len(selected) == 2 and all(r["video_id"] != 2967 for r in selected)
    output.mkdir(parents=True)
    results = []
    for row in selected:
        if digest(row["config_file"]) != row["config_sha256"]:
            raise ValueError("Frozen configuration changed")
        print("Repeat", row["event_id"], flush=True)
        dest = output / row["name"]
        args = make_parser().parse_args(
            [
                "--baseline",
                row["baseline"],
                "--config",
                row["config_file"],
                "--data-root",
                plan["data_root"],
                "--device",
                "cuda:0",
                "--output",
                str(dest),
            ]
        )
        with (output / f"{row['event_id']}.log").open(
            "w", encoding="utf-8"
        ) as stream, redirect_stdout(stream), redirect_stderr(stream):
            run_recovery(args)
            checked = compare_verified(
                Path(row["folder"]), dest, Path(plan["data_root"])
            )
        results.append({"event_id": row["event_id"], **checked})
        write_json(dest / "repeat-verification.json", checked)
        write_json(
            output / "verification.json",
            {
                "status": "running" if len(results) < 2 else "passed",
                "events": results,
                "primary_cohort": str(cohort.resolve()),
            },
        )
        gc.collect()
        torch.cuda.empty_cache()
        print(row["event_id"], "exact repeat passed", flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    execute(a.cohort, a.output)


if __name__ == "__main__":
    main()
