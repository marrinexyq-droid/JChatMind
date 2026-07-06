import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "verify_rag_canary.py"


def load_verify_module():
    spec = importlib.util.spec_from_file_location("verify_rag_canary", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["verify_rag_canary"] = module
    spec.loader.exec_module(module)
    return module


def args(**overrides):
    values = {
        "skip_python_tests": False,
        "skip_acceptance": False,
        "skip_java_tests": False,
        "acceptance_rounds": 3,
        "acceptance_output_json": Path("rag-mcp/output/metrics/test_acceptance.json"),
        "java_test_expression": "!JChatMindV1Test,!JChatMindV2Test",
        "report_json": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_run_verification_builds_project_level_commands():
    module = load_verify_module()
    calls = []

    def fake_runner(command, cwd, env, text, capture_output, check):
        calls.append({"command": command, "cwd": cwd, "env": env})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(args(), runner=fake_runner)

    assert report["status"] == "passed"
    assert [step["name"] for step in report["steps"]] == [
        "python_tests",
        "canary_acceptance",
        "java_bridge_tests",
    ]
    assert calls[0]["command"][1:] == ["-m", "pytest", "-q"]
    assert calls[0]["cwd"].name == "rag-mcp"
    assert "PYTHONPATH" in calls[0]["env"]
    assert calls[1]["command"][1:4] == [
        "scripts/canary_acceptance.py",
        "--ragas-rounds",
        "3",
    ]
    assert calls[2]["cwd"].name == "jchatmind"
    assert calls[2]["command"][-2:] == ["-Dtest=!JChatMindV1Test,!JChatMindV2Test", "test"]


def test_run_verification_reports_failed_step_without_stopping():
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            return subprocess.CompletedProcess(command, 1, stdout="bad", stderr="failed")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(args(), runner=fake_runner)

    assert report["status"] == "failed"
    statuses = {step["name"]: step["status"] for step in report["steps"]}
    assert statuses["python_tests"] == "passed"
    assert statuses["canary_acceptance"] == "failed"
    assert statuses["java_bridge_tests"] == "passed"


def test_run_verification_honors_skip_flags():
    module = load_verify_module()
    calls = []

    def fake_runner(command, cwd, env, text, capture_output, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(skip_python_tests=True, skip_java_tests=True),
        runner=fake_runner,
    )

    assert [step["status"] for step in report["steps"]] == [
        "skipped",
        "passed",
        "skipped",
    ]
    assert len(calls) == 1
    assert any("canary_acceptance.py" in part for part in calls[0])
