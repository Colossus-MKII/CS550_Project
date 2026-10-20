"""The scientific workspace must run without the teaching website or its paths."""

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tracking_lab import PACKAGE_ROOT, ROOT
from tracking_lab.common import digest
from tracking_lab.run import make_parser
from tracking_lab.runtime import environment, resolve_data_root


def test_default_paths_are_inside_independent_workspace():
    args = make_parser().parse_args([])
    assert args.samples == ROOT / "data/stage1"
    assert args.weights_dir == ROOT / "checkpoints"
    assert args.trackeval_root == ROOT / "external/TrackEval"
    assert args.output.is_relative_to(ROOT / "runs")
    assert args.selection.is_relative_to(PACKAGE_ROOT / "defaults")
    assert args.device == "cuda:0"


def test_scientific_code_has_no_teaching_import_or_timestamp_path():
    for path in PACKAGE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] not in {"learning", "pilot"}
                    for alias in node.names
                ), path
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] not in {
                    "learning",
                    "pilot",
                }, path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert (
                    "outputs/learning" not in node.value
                    and "20261011-095748" not in node.value
                ), path


def test_import_from_unrelated_directory_is_read_only(tmp_path):
    workspace = tmp_path / "different-machine"
    workspace.mkdir()
    env = {**os.environ, "CS550_EXPERIMENT_HOME": str(workspace)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            'import tracking_lab,sys,json; print(json.dumps({"root":str(tracking_lab.ROOT),"torch":"torch" in sys.modules,"learning":"learning" in sys.modules}))',
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    value = json.loads(result.stdout)
    assert value == {
        "root": str(workspace.resolve()),
        "torch": False,
        "learning": False,
    }
    assert not list(workspace.iterdir())


def test_cli_help_needs_neither_dataset_nor_website(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "tracking_lab.run", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--data-root" in result.stdout and "--trackeval-root" in result.stdout


def test_relocated_run_uses_relative_data_or_explicit_override(tmp_path):
    data = tmp_path / "data/stage1"
    data.mkdir(parents=True)
    (data / "manifest.json").write_text("{}", encoding="utf-8")
    run = tmp_path / "runs/example"
    run.mkdir(parents=True)
    summary = {
        "data_root_relative_to_run": "../../data/stage1",
        "samples_root": "Z:/old-machine/absent",
        "sample_manifest_sha256": digest(data / "manifest.json"),
    }
    assert resolve_data_root(run, summary) == data
    assert resolve_data_root(run, {"samples_root": "missing"}, data) == data
    (data / "manifest.json").write_text('{"changed":1}', encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_data_root(run, summary)


def test_gpu_is_not_restricted_to_a_3080(monkeypatch):
    import torch
    import tracking_lab.runtime as runtime

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "set_device", lambda device: None)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    monkeypatch.setattr(
        torch.cuda, "get_device_name", lambda device: "NVIDIA RTX A4000"
    )
    monkeypatch.setattr(
        torch.cuda,
        "get_device_properties",
        lambda device: SimpleNamespace(total_memory=16 * 2**30),
    )
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda device: (8, 6))
    monkeypatch.setattr(runtime, "sam_source_metadata", lambda: {"reviewed": True})
    result = environment("cuda:0")
    assert (
        result["device"] == "NVIDIA RTX A4000" and result["logical_device"] == "cuda:0"
    )
