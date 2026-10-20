"""Portable experiment package. Importing it does not load models or create files."""

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
_source_workspace = PACKAGE_ROOT.parent
ROOT = (
    Path(
        os.environ.get(
            "CS550_EXPERIMENT_HOME",
            str(
                _source_workspace
                if (_source_workspace / "pyproject.toml").is_file()
                else Path.cwd()
            ),
        )
    )
    .expanduser()
    .resolve()
)


def configure_runtime():
    """Keep detector settings inside this experiment workspace, not a user profile."""
    folder = ROOT / ".cache/ultralytics"
    folder.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(folder)
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
