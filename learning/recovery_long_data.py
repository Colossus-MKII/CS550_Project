"""Import a reviewed long-window study without model/runtime imports.

The 8-step archive stays active and immutable. This separate manifest extends
it with two completed 30-step runs, their repeat proofs and curated media.
Never copy raw summaries (private absolute paths), masks or arbitrary folders.
"""

import argparse
import csv
import json
from pathlib import Path
import re
import shutil

from .recovery_page import CODE, EVENTS, GROUPS, digest, read_json, read_recovery

PAGES = ("recovery-long.html", "recovery-long.en.html")
CODE_LONG = (*CODE, "association_trace.py", "sam_baseline.py", "bytetrack.py")
TABLES = (
    "checkpoint-scores.csv",
    "checkpoint-pairs.csv",
    "prompt-timeline.csv",
    "assignment-candidates.csv",
    "frame-curves.csv",
)


def safe_name(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Unsafe long-window name")
    return value


def verify_csv(scores, runs):
    """Reject inconsistent checkpoint displays; read saved curves, no inference."""
    expected = {
        (mode, event, condition, group, window)
        for mode in ("normal", "skip")
        for event in EVENTS
        for condition in ("yolo", "reference")
        for group in GROUPS
        for window in (8, 20, 30)
    }
    actual = [
        (r["mode"], r["event"], r["condition"], r["group"], int(r["window"]))
        for r in scores
    ]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Incomplete long-window checkpoints")
    for row, key in zip(scores, actual):
        mode, event, condition, group, window = key
        curve = runs[mode]["curves"][f"{event}/{condition}/{group}"]["curve"][:window]
        visible = [r for r in curve if r["visible"]]
        mean = sum(r["mask_iou"] for r in visible) / len(visible)
        if (
            abs(mean - float(row["mean_visible_mask_iou"])) > 1e-12
            or sum(r["correct"] for r in visible) != int(row["correct_visible_steps"])
            or len(visible) != int(row["visible_steps"])
            or max(r["success_streak"] for r in curve)
            != int(row["longest_correct_streak"])
        ):
            raise ValueError("Checkpoint disagrees with saved curve")


def import_long(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    previous = read_recovery(output)
    if not previous:
        raise ValueError("Import the reviewed 8-step H/R batch first")
    checks = read_json(study / "study-verification.json")
    final = read_json(study / "final-verification.json")
    if checks["status"] != "passed" or final["status"] != "passed":
        raise ValueError("Unverified long-window study")
    if digest(study / "study-verification.json") != final["study_verification_sha256"]:
        raise ValueError("Study proof fingerprint differs")
    if Path(checks["previous_run"]).name != previous["run"]:
        raise ValueError("Long-window predecessor differs")
    if checks["run_summary_sha256"][checks["previous_run"]] not in (
        previous["repeat"]["first_summary_sha256"],
        previous["repeat"]["second_summary_sha256"],
    ):
        raise ValueError("Long-window 8-step source fingerprint differs")
    if len(checks["compatibility_checks"]) != 16 or not all(
        r["old_8_steps_exact"] for r in checks["compatibility_checks"]
    ):
        raise ValueError("Old 8-step outputs changed")
    destination = output / "recovery-long-results" / safe_name(study.name)
    files, runs, associations, pending = {}, {}, {}, []

    def copy(src, relative):
        target = destination / relative
        if target.exists() and digest(target) != digest(src):
            raise ValueError("Refuse to overwrite different long-window evidence")
        # Reject bad evidence before exposing any newly copied artifact.
        files[relative] = digest(src)
        pending.append((src, target))

    for mode in ("normal", "skip"):
        source = Path(checks[mode + "_run"])
        safe_name(source.name)
        summary = read_json(source / "summary.json")
        verification = read_json(source / "verification.json")
        repeat = next(r for r in final["repeat_checks"] if r["run"] == source.name)
        if (
            summary["status"] != "completed"
            or verification["status"] != "passed"
            or repeat["status"] != "passed"
            or repeat["branches"] != 16
            or repeat["state_traces_exact"] != 16
            or digest(source / "summary.json") != repeat["first_summary_sha256"]
            or digest(source / "summary.json")
            != checks["run_summary_sha256"][str(source)]
        ):
            raise ValueError("Repeat proof does not cover long-window run")
        if summary["baseline_summary_sha256"] != previous[
            "baseline_summary_sha256"
        ] or any(
            summary["synchronized_reference"]["historical_B0_different_frames"].values()
        ):
            raise ValueError("Long-window baseline differs")
        config = summary["configuration"]
        if (
            config["window"],
            config["mask_iou_threshold"],
            config["streak_required"],
            config["report_windows"],
        ) != (30, 0.5, 3, [8, 20, 30]):
            raise ValueError("Unreviewed long-window rules")
        if config["sam_skip_next_refresh"] is not (mode == "skip") or config[
            "conditions"
        ] != ["yolo", "reference"]:
            raise ValueError("Long-window refresh conditions differ")
        if len(summary["events"]) != 2 or {
            (e["name"], e["video_id"], e["gt_id"], e["frame"])
            for e in summary["events"]
        } != {
            (e["name"], e["video_id"], e["gt_id"], e["frame"])
            for e in previous["events"]
        }:
            raise ValueError("Unreviewed long-window events")
        expected = {
            (e, c, g) for e in EVENTS for c in ("yolo", "reference") for g in GROUPS
        }
        actual = [(r["event"], r["condition"], r["group"]) for r in summary["branches"]]
        if len(actual) != 16 or set(actual) != expected:
            raise ValueError("Incomplete long-window branches")
        prefix, curves, lifecycle = "runs/" + source.name + "/", {}, []
        for record in summary["branches"]:
            folder = f'{record["event"]}/{record["condition"]}/{record["group"]}'
            if record["folder"] != folder:
                raise ValueError("Unsafe long-window branch path")
            result = read_json(source / folder / "recovery.json")
            if any(record[k] != v for k, v in result["summary"].items()):
                raise ValueError("Long-window scores disagree with curves")
            if len(result["curve"]) != 30:
                raise ValueError("Incomplete long-window curve")
            curves[folder] = result
            copy(source / folder / "recovery.json", prefix + folder + "/recovery.json")
            # Extract only relevant diagnostics; never expose full raw histories.
            if mode == "normal":
                trace = read_json(source / folder / "state-trace.json")
                for row in trace:
                    if (
                        record["event"] == "equestrian-person-poor-mask"
                        and record["group"].startswith("A")
                        and row["frame"] in (17, 18, 29)
                    ):
                        associations[
                            f'{record["condition"]}/{record["group"]}/{row["frame"]}'
                        ] = next(
                            x["stages"]
                            for x in row["assignments"]
                            if x["category"] == "person"
                        )
                    if (
                        record["event"] == "cat-stable-control"
                        and record["group"].startswith("B")
                        and row["frame"] in (20, 25, 35, 36, 45, 50)
                    ):
                        identity = record["prediction_id"]
                        lifecycle.append(
                            {
                                "condition": record["condition"],
                                "group": record["group"],
                                "frame": row["frame"],
                                "active": identity in row["active_ids"],
                                "output": identity in row["output_ids"],
                                "actions": [
                                    a for a in row["actions"] if a.get("id") == identity
                                ],
                            }
                        )
        for event in summary["events"]:
            for condition in ("yolo", "reference"):
                base = f'visuals/{event["name"]}-{condition}'
                for ending in (
                    "curves.png",
                    "four-groups.mp4",
                    *(f'step{event["frame"]+i}.png' for i in (1, 3, 30)),
                ):
                    relative = base + "-" + ending
                    if ending.endswith(".mp4"):
                        proof = next(
                            r
                            for r in final["video_checks"]
                            if r["run"] == source.name
                            and r["file"] == Path(relative).name
                        )
                        if (
                            proof["decoded_frames"] != 33
                            or digest(source / relative) != proof["sha256"]
                        ):
                            raise ValueError("Video proof fingerprint differs")
                    copy(source / relative, prefix + relative)
        for name in CODE_LONG:
            relative = "code/" + name + ".txt"
            if digest(source / relative) != summary["source_sha256"][name]:
                raise ValueError("Long-window code snapshot differs")
            copy(source / relative, prefix + relative)
        for name in ("config.json", "verification.json"):
            copy(source / name, prefix + name)
        runs[mode] = {
            "run": source.name,
            "prefix": prefix,
            "configuration": config,
            "events": summary["events"],
            "branches": summary["branches"],
            "curves": curves,
            "verification": verification,
            "repeat": repeat,
            "lifecycle": lifecycle,
        }
    for name in TABLES:
        copy(study / name, name)
    for event in EVENTS:
        for condition in ("yolo", "reference"):
            name = f"{event}-{condition}-refresh-curves.png"
            copy(study / name, name)
    copy(study / "final-verification.json", "final-verification.json")
    with (study / "checkpoint-scores.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        scores = list(csv.DictReader(stream))
    verify_csv(scores, runs)
    normal_cfg, skip_cfg = (dict(runs[m]["configuration"]) for m in ("normal", "skip"))
    for cfg in (normal_cfg, skip_cfg):
        cfg.pop("role")
        cfg.pop("sam_skip_next_refresh")
    if normal_cfg != skip_cfg:
        raise ValueError("More than one experimental condition changed")
    data = {
        "kind": "verified-long-rider-cat-hr",
        "run": safe_name(study.name),
        "prefix": f"recovery-long-results/{study.name}/",
        "previous_run": previous["run"],
        "baseline_run": previous["baseline_run"],
        "runs": runs,
        "scores": scores,
        "associations": associations,
        "checks": {k: checks[k] for k in ("compatibility_checks", "treatment_checks")},
        "final": final,
        "files": files,
    }
    public = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    archived = destination / "evidence.json"
    if archived.exists() and archived.read_text(encoding="utf-8") != public:
        raise ValueError("Refuse to replace archived long-window manifest")
    active = output / "recovery-long-results/manifest.json"
    if active.exists() and read_json(active)["run"] != data["run"]:
        raise ValueError("Keep prior long-window manifest; explicit migration required")
    for src, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(src, target)
    archived.write_text(public, encoding="utf-8")
    active.write_text(public, encoding="utf-8")
    # Existing server allows text downloads, not CSV. Preserve the server.
    for name in TABLES:
        shutil.copy2(destination / name, destination / (name + ".txt"))
    return data


def read_long(output):
    path = Path(output) / "recovery-long-results/manifest.json"
    if not path.exists():
        return None
    data = read_json(path)
    if not re.fullmatch(r"recovery-long-results/[A-Za-z0-9_-]+/", data["prefix"]):
        raise ValueError("Unsafe long-window evidence prefix")
    previous = read_recovery(output)
    if (
        not previous
        or previous["run"] != data["previous_run"]
        or previous["baseline_run"] != data["baseline_run"]
    ):
        raise ValueError("Long-window predecessor/baseline no longer matches")
    root = Path(output) / data["prefix"]
    if read_json(root / "evidence.json") != data:
        raise ValueError("Long-window archive differs from manifest")
    for name, fingerprint in data["files"].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or digest(target) != fingerprint:
            raise ValueError("Long-window evidence fingerprint differs: " + name)
        if name.endswith(".csv") and digest(root / (name + ".txt")) != fingerprint:
            raise ValueError("Long-window CSV alias fingerprint differs")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print("Imported long-window study:", import_long(args.study, args.output)["run"])
