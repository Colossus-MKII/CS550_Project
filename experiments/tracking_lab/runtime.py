"""Hardware, dependency and resource checks shared by Windows and Linux entrypoints."""

import importlib.metadata
import json
from pathlib import Path
import platform
import random
import subprocess
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from . import ROOT, PACKAGE_ROOT
from .common import digest

SAM_REV = "2b90b9f5ceec907a1c18123530e92e794ad901a4"


def checked_weight(name, weights_dir=None, manifest_path=None):
    path = Path(weights_dir or ROOT / "checkpoints") / name
    manifest_path = Path(manifest_path or PACKAGE_ROOT / "defaults/checkpoints.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = next(row for row in manifest if Path(row["File"]).name == name)
    actual = digest(path)
    if (
        actual.lower() != expected["SHA256"].lower()
        or path.stat().st_size != expected["Bytes"]
    ):
        raise RuntimeError(f"Checkpoint fingerprint differs: {name}")
    return path, actual


def sam_source_metadata():
    raw = importlib.metadata.distribution("SAM-2").read_text("direct_url.json")
    source = json.loads(raw or "{}")
    if (
        SAM_REV in source.get("url", "")
        or source.get("vcs_info", {}).get("commit_id") == SAM_REV
    ):
        return source
    # Editable installs on iLab may record a local git directory instead of a URL.
    url = urlsplit(source.get("url", ""))
    if url.scheme == "file":
        folder = Path(url2pathname(unquote(url.path)))
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(folder), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = subprocess.check_output(
                ["git", "-C", str(folder), "diff", "--name-only"], text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            revision, dirty = None, None
        if revision == SAM_REV and not dirty:
            return {**source, "verified_git_revision": revision}
    raise RuntimeError(
        f"Install the reviewed SAM 2 revision {SAM_REV}; source provenance is missing or different"
    )


def environment(device_choice="cuda:0", seed=550):
    import numpy as np
    import torch

    device = torch.device(device_choice)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; there is no silent CPU fallback")
    torch.cuda.set_device(device)
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError(
            "This protocol requires BF16 support; do not silently change SAM precision"
        )
    names = (
        "torch",
        "torchvision",
        "ultralytics",
        "SAM-2",
        "numpy",
        "scipy",
        "Pillow",
        "opencv-python",
        "lap",
        "imageio-ffmpeg",
    )
    versions = {name: importlib.metadata.version(name) for name in names}
    if versions["ultralytics"] != "8.3.221":
        raise RuntimeError("Expected reviewed Ultralytics 8.3.221 API")
    source = sam_source_metadata()
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return {
        "device": torch.cuda.get_device_name(device),
        "logical_device": str(device),
        "device_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
        "capability": list(torch.cuda.get_device_capability(device)),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "versions": versions,
        "torch_cuda": torch.version.cuda,
        "sam_source": source,
        "sam_revision": SAM_REV,
        "tf32": False,
        "seed": seed,
        "determinism": "seeded; GPU floating point is not claimed bitwise reproducible",
    }


def resolve_data_root(output, summary, override=None):
    """A moved run uses an explicit override or a portable run-relative data path."""
    candidates = []
    if override is not None:
        candidates.append(Path(override))
    else:
        relative = summary.get("data_root_relative_to_run")
        if relative:
            candidates.append(Path(output) / relative)
        if summary.get("samples_root"):
            candidates.append(Path(summary["samples_root"]))
    for folder in candidates:
        manifest = folder / "manifest.json"
        if manifest.is_file():
            expected = summary.get("sample_manifest_sha256")
            if expected and digest(manifest) != expected:
                raise ValueError(
                    "Selected data manifest differs from the recorded input"
                )
            return folder.resolve()
    raise FileNotFoundError(
        "Input data not found after relocation; pass --data-root /path/to/prepared-data"
    )
