"""Keep editor launches consistent with the portable module entry point."""

import json
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[1]


def read_config(name):
    return json.loads((WORKSPACE / ".vscode" / name).read_text(encoding="utf-8"))


def test_editor_defaults_and_extension_recommendations():
    settings = read_config("settings.json")
    interpreter = settings["python.defaultInterpreterPath"]
    assert ".." not in interpreter and "${" not in interpreter
    assert interpreter.endswith("/.venv/Scripts/python.exe")
    assert settings["python.testing.pytestArgs"] == ["tests"]
    assert set(read_config("extensions.json")["recommendations"]) == {
        "ms-python.python",
        "ms-python.debugpy",
        "ms-python.vscode-pylance",
    }


@pytest.mark.parametrize("index", [0, 1])
def test_launch_uses_module_and_keeps_old_results(index):
    launch = read_config("launch.json")["configurations"][index]
    assert launch["type"] == "debugpy"
    assert launch["request"] == "launch"
    assert launch["module"] == "tracking_lab.run"
    assert "program" not in launch
    assert launch["cwd"] == "${workspaceFolder}"
    assert launch["console"] == "internalConsole"
    assert launch["windows"]["python"] == ("${config:python.defaultInterpreterPath}")
    assert launch["env"]["CS550_EXPERIMENT_HOME"] == "${workspaceFolder}"
    assert "--output" not in launch["args"]
    assert ("--check" in launch["args"]) == (index == 1)
    if index == 0:
        assert launch["stopOnEntry"] is True


def test_tasks_call_python_without_shell_or_policy_changes():
    tasks = read_config("tasks.json")["tasks"]
    for task in tasks:
        assert task["type"] == "process"
        assert task["options"]["cwd"] == "${workspaceFolder}"
        assert task["windows"]["command"] == ("${config:python.defaultInterpreterPath}")
    assert tasks[0]["args"][:3] == ["-m", "tracking_lab.run", "--check"]
    assert tasks[0]["group"] == {"kind": "build", "isDefault": True}


@pytest.mark.parametrize("index", [2, 3])
def test_recovery_launches_use_same_interpreter_and_new_output(index):
    launch = read_config("launch.json")["configurations"][index]
    assert launch["module"] == "tracking_lab.recovery"
    assert launch["cwd"] == "${workspaceFolder}"
    assert launch["windows"]["python"] == "${config:python.defaultInterpreterPath}"
    assert "--output" not in launch["args"]
    assert ("--check" in launch["args"]) == (index == 3)
    if index == 2:
        assert launch["stopOnEntry"]
