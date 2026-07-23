import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest


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
        "strict_cutover": False,
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


def test_strict_cutover_runs_each_live_round_and_aggregates_reports(tmp_path):
    module = load_verify_module()
    calls = []
    output_json = tmp_path / "acceptance.json"

    def fake_runner(command, cwd, env, text, capture_output, check):
        calls.append(command)
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            round_number = len(
                [
                    call
                    for call in calls
                    if any("canary_acceptance.py" in part for part in call)
                ]
            )
            report_path.write_text(
                json.dumps({"status": "passed", "round": round_number}),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=3,
            acceptance_output_json=output_json,
        ),
        runner=fake_runner,
    )

    acceptance_calls = [
        call
        for call in calls
        if any("canary_acceptance.py" in part for part in call)
    ]
    assert len(acceptance_calls) == 3
    assert acceptance_calls[0][1:-2] == [
        "scripts/canary_acceptance.py",
        "--ragas-rounds",
        "1",
        "--require-chroma",
        "--current-pipeline",
        "--answer-policy",
        "generated",
        "--java-baseline-report",
        str(module.DEFAULT_JAVA_BASELINE_REPORT),
    ]
    assert Path(acceptance_calls[0][-1]).name == "acceptance.round-1.json"
    assert Path(acceptance_calls[1][-1]).name == "acceptance.round-2.json"
    assert Path(acceptance_calls[2][-1]).name == "acceptance.round-3.json"
    assert sum(command[1:3] == ["-m", "pytest"] for command in calls) == 1
    assert sum(command[-1:] == ["test"] for command in calls) == 1
    assert report["status"] == "passed"
    assert report["version"] == "3.0"
    assert report["strict_cutover"] is True
    assert datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00")).tzinfo
    assert report["source_attestation_stable"] is True
    assert report["source_attestation_error"] is None
    attestation = report["source_attestation"]
    assert attestation["version"] == "source-tree-v1"
    assert len(attestation["sha256"]) == 64
    assert set(attestation["groups"]) == {
        "python_runtime",
        "java_bridge",
        "config",
        "gates",
        "tests",
        "lockfiles",
        "evaluation_data",
    }
    assert (
        "rag-mcp/data/evaluation/java_current_pipeline_baseline.json"
        in attestation["excluded_paths"]
    )
    assert report["burn_in"] == {
        "requested_rounds": 3,
        "completed_rounds": 3,
        "rounds": [
            {
                "round": 1,
                "step_status": "passed",
                "report_path": str(tmp_path / "acceptance.round-1.json"),
                "report": {"status": "passed", "round": 1},
            },
            {
                "round": 2,
                "step_status": "passed",
                "report_path": str(tmp_path / "acceptance.round-2.json"),
                "report": {"status": "passed", "round": 2},
            },
            {
                "round": 3,
                "step_status": "passed",
                "report_path": str(tmp_path / "acceptance.round-3.json"),
                "report": {"status": "passed", "round": 3},
            },
        ],
    }


def test_strict_cutover_with_fewer_than_three_rounds_cannot_pass(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=2,
            acceptance_output_json=tmp_path / "acceptance.json",
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 2


def test_strict_cutover_ignores_narrowed_java_test_expression(tmp_path):
    module = load_verify_module()
    calls = []

    def fake_runner(command, cwd, env, text, capture_output, check):
        calls.append(command)
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_output_json=tmp_path / "acceptance.json",
            java_test_expression="PythonRagBridgeConfigurationFilesTest",
        ),
        runner=fake_runner,
    )

    java_command = next(command for command in calls if command[-1:] == ["test"])
    assert f"-Dtest={module.DEFAULT_JAVA_TEST_EXPRESSION}" in java_command
    assert report["status"] == "passed"


def test_strict_cutover_sanitizes_test_selection_environment(monkeypatch):
    module = load_verify_module()
    unsafe_variables = [
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONOPTIMIZE",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
        "PYTHONWARNINGS",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "MAVEN_ARGS",
        "MAVEN_OPTS",
        "MAVEN_CONFIG",
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "_JAVA_OPTIONS",
    ]
    for name in unsafe_variables:
        monkeypatch.setenv(name, "unsafe-selection-override")
    calls = []

    def fake_runner(command, cwd, env, text, capture_output, check):
        calls.append({"command": command, "cwd": cwd, "env": env})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    module.run_verification(
        args(strict_cutover=True, skip_acceptance=True),
        runner=fake_runner,
    )

    python_call = next(call for call in calls if call["cwd"] == module.RAG_MCP_DIR)
    java_call = next(call for call in calls if call["cwd"] == module.JCHATMIND_DIR)
    for name in unsafe_variables:
        if name != "PYTHONPATH":
            assert python_call["env"].get(name) is None
        assert java_call["env"].get(name) is None
    assert python_call["env"]["PYTHONNOUSERSITE"] == "1"
    assert python_call["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert "unsafe-selection-override" not in python_call["env"]["PYTHONPATH"]


def test_strict_cutover_fails_when_round_report_is_missing(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"] == {
        "requested_rounds": 1,
        "completed_rounds": 0,
        "rounds": [
            {
                "round": 1,
                "step_status": "failed",
                "report_path": str(tmp_path / "acceptance.round-1.json"),
                "report": None,
            }
        ],
    }


def test_strict_cutover_fails_when_round_report_is_invalid_json(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text("{not-json", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"][0]["step_status"] == "failed"
    assert report["burn_in"]["rounds"][0]["report"] is None


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity"])
def test_strict_cutover_rejects_non_finite_round_report(tmp_path, non_finite):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text(
                f'{{"status":"passed","unexpected_metric":{non_finite}}}',
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"][0]["step_status"] == "failed"
    assert report["burn_in"]["rounds"][0]["report"] is None
    assert "non-finite JSON number" in report["steps"][1]["artifact_error"]


def test_strict_cutover_rejects_overflowing_round_report_number(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text(
                '{"status":"passed","unexpected_metric":1e400}',
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"][0]["step_status"] == "failed"
    assert report["burn_in"]["rounds"][0]["report"] is None
    assert "non-finite JSON number" in report["steps"][1]["artifact_error"]


def test_strict_cutover_fails_when_round_report_is_invalid_utf8(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_bytes(b"\xff\xfe")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["rounds"][0]["report"] is None


def test_verifier_invalidates_stale_final_report_before_running(tmp_path):
    module = load_verify_module()
    report_path = tmp_path / "verification.json"
    report_path.write_text('{"status":"passed"}', encoding="utf-8")

    def failing_runner(command, cwd, env, text, capture_output, check):
        raise RuntimeError("runner crashed")

    with pytest.raises(RuntimeError, match="runner crashed"):
        module.run_verification(
            args(report_json=report_path),
            runner=failing_runner,
        )

    assert not report_path.exists()


def test_verifier_refuses_to_write_non_finite_report(tmp_path, monkeypatch):
    module = load_verify_module()
    report_path = tmp_path / "verification.json"

    def non_finite_step(spec, runner):
        return {
            "name": spec.name,
            "status": "passed",
            "duration_ms": float("nan"),
        }

    monkeypatch.setattr(module, "run_step", non_finite_step)

    with pytest.raises(ValueError, match="Out of range float values"):
        module.run_verification(
            args(report_json=report_path),
        )

    assert not report_path.exists()
    assert not module.atomic_temp_path(report_path).exists()


def test_cli_accepts_strict_cutover_and_defaults_verification_report(monkeypatch):
    module = load_verify_module()
    captured = {}

    def fake_verification(parsed_args):
        captured["args"] = parsed_args
        return {"status": "passed"}

    monkeypatch.setattr(module, "run_verification", fake_verification)

    exit_code = module.main(["--strict-cutover", "--acceptance-rounds", "2"])

    assert exit_code == 0
    assert captured["args"].strict_cutover is True
    assert captured["args"].acceptance_rounds == 2
    assert captured["args"].report_json == Path(
        "rag-mcp/output/metrics/rag_canary_verification.json"
    )


def test_cli_refuses_to_print_non_finite_report(monkeypatch, capsys):
    module = load_verify_module()
    monkeypatch.setattr(
        module,
        "run_verification",
        lambda _args: {"status": "passed", "unexpected_metric": float("inf")},
    )

    with pytest.raises(ValueError, match="Out of range float values"):
        module.main([])

    assert "Infinity" not in capsys.readouterr().out


def test_strict_cutover_does_not_reuse_a_stale_round_report(tmp_path):
    module = load_verify_module()
    stale_report = tmp_path / "acceptance.round-1.json"
    stale_report.write_text('{"status":"passed","stale":true}', encoding="utf-8")

    def fake_runner(command, cwd, env, text, capture_output, check):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"][0]["report"] is None


def test_strict_cutover_fails_when_acceptance_is_skipped():
    module = load_verify_module()

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=2,
            skip_python_tests=True,
            skip_acceptance=True,
            skip_java_tests=True,
        ),
    )

    assert report["status"] == "failed"
    assert report["burn_in"] == {
        "requested_rounds": 2,
        "completed_rounds": 0,
        "rounds": [],
    }


@pytest.mark.parametrize("skip_flag", ["skip_python_tests", "skip_java_tests"])
def test_strict_cutover_fails_when_required_test_suite_is_skipped(tmp_path, skip_flag):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            **{skip_flag: True},
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 1


def test_strict_cutover_fails_when_round_report_status_is_not_passed(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text('{"status":"failed"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"] == [
        {
            "round": 1,
            "step_status": "failed",
            "report_path": str(tmp_path / "acceptance.round-1.json"),
            "report": {"status": "failed"},
        }
    ]


def test_strict_cutover_does_not_complete_a_failed_process_round(tmp_path):
    module = load_verify_module()

    def fake_runner(command, cwd, env, text, capture_output, check):
        if any("canary_acceptance.py" in part for part in command):
            report_path = Path(command[command.index("--output-json") + 1])
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="failed",
                stderr="acceptance failed",
            )
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = module.run_verification(
        args(
            strict_cutover=True,
            acceptance_rounds=1,
            acceptance_output_json=tmp_path / "acceptance.json",
            skip_python_tests=True,
            skip_java_tests=True,
        ),
        runner=fake_runner,
    )

    assert report["status"] == "failed"
    assert report["burn_in"]["completed_rounds"] == 0
    assert report["burn_in"]["rounds"][0]["step_status"] == "failed"
    assert report["burn_in"]["rounds"][0]["report"] == {"status": "passed"}


@pytest.mark.parametrize("invalid_rounds", [0, -1])
def test_run_verification_rejects_non_positive_acceptance_rounds(invalid_rounds):
    module = load_verify_module()

    def unexpected_runner(*args, **kwargs):
        raise AssertionError("validation must happen before subprocess execution")

    with pytest.raises(ValueError, match="acceptance_rounds must be at least 1"):
        module.run_verification(
            args(strict_cutover=True, acceptance_rounds=invalid_rounds),
            runner=unexpected_runner,
        )


def test_cli_rejects_non_positive_acceptance_rounds(monkeypatch):
    module = load_verify_module()

    def unexpected_verification(_args):
        raise AssertionError("argparse must reject the invalid round count")

    monkeypatch.setattr(module, "run_verification", unexpected_verification)

    with pytest.raises(SystemExit) as exc_info:
        module.main(["--acceptance-rounds", "0"])

    assert exc_info.value.code == 2
