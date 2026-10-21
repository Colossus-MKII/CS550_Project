"""Build a source-only website preview without models or saved experiment assets."""

import argparse
import json
from pathlib import Path

from .report import write_report


def build_preview(output):
    """Create a fresh preview directory, refusing to overwrite any existing run."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Preview destination already exists: {output}")
    output.mkdir(parents=True)
    summary = {
        "status": "source-preview",
        "preview_only": True,
        "source": "Website source preview; saved measurements and media are not bundled.",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_report(output, summary)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs/learning/source-preview",
        help="New destination directory; existing directories are never overwritten",
    )
    args = parser.parse_args()
    try:
        output = build_preview(args.output)
    except FileExistsError as error:
        parser.error(str(error))
    print(f"Source-only website preview: {output / 'index.html'}")
    print("Saved experiment measurements and media are not included; no models ran.")


if __name__ == "__main__":
    main()
