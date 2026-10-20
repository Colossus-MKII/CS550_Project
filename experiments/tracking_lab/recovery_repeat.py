"""Read-only numerical repeatability check of two complete recovery runs."""

import argparse
import json
from pathlib import Path

from .common import load_predictions, write_json, digest
from .recovery import assert_same_predictions


def compare(first, second):
    first, second = Path(first), Path(second)
    left = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    right = json.loads((second / "summary.json").read_text(encoding="utf-8"))
    assert left["status"] == right["status"] == "completed"
    assert left["configuration"] == right["configuration"]

    def keyed(summary):
        return {
            (r["event"], r["condition"], r["group"]): r for r in summary["branches"]
        }

    a, b = keyed(left), keyed(right)
    assert set(a) == set(b)
    frames = masks = 0
    for key in a:
        x, y = a[key], b[key]
        assert x["correction"] == y["correction"]
        assert x["prediction_id"] == y["prediction_id"]
        p, q = first / x["folder"], second / y["folder"]
        assert json.loads((p / "recovery.json").read_text()) == json.loads(
            (q / "recovery.json").read_text()
        )
        aa, bb = load_predictions(p), load_predictions(q)
        assert len(aa) == len(bb)
        for expected, actual in zip(aa, bb):
            assert_same_predictions(expected, actual)
            frames += 1
            masks += len(actual)
    return {
        "status": "passed",
        "branches": len(a),
        "saved_branch_frames": frames,
        "masks_compared": masks,
        "comparison": "IDs, classes, scores, boxes and binary masks exact; all recovery summaries/curves exact",
        "first_summary_sha256": digest(first / "summary.json"),
        "second_summary_sha256": digest(second / "summary.json"),
        "scope": "Observed repeatability on this local setup, not a universal bitwise determinism guarantee",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    parser.add_argument("--write-record", action="store_true")
    args = parser.parse_args(argv)
    result = compare(args.first, args.second)
    if args.write_record:
        write_json(args.second / "repeat-verification.json", result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
