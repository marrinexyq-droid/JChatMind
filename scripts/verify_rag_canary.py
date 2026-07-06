from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_MCP_DIR = REPO_ROOT / "rag-mcp"
JCHATMIND_DIR = REPO_ROOT / "jchatmind"
DEFAULT_JAVA_TEST_EXPRESSION = "!JChatMindV1Test,!JChatMindV2Test"
DEFAULT_ACCEPTANCE_OUTPUT = Path("rag-mcp/output/metrics/canary_acceptance_report.json")


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class StepSpec:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None


def run_verification(args: argparse.Namespace, runner: Runner = subprocess.run) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    if args.skip_python_tests:
        steps.append(skipped_step("python_tests"))
    else:
        steps.append(
            run_step(
                StepSpec(
                    name="python_tests",
                    command=[sys.executable, "-m", "pytest", "-q"],
                    cwd=RAG_MCP_DIR,
                    env=python_env(),
                ),
                runner,
            )
        )

    if args.skip_acceptance:
        steps.append(skipped_step("canary_acceptance"))
    else:
        acceptance_output = resolve_repo_path(args.acceptance_output_json)
        steps.append(
            run_step(
                StepSpec(
                    name="canary_acceptance",
                    command=[
                        sys.executable,
                        "scripts/canary_acceptance.py",
                        "--ragas-rounds",
                        str(args.acceptance_rounds),
                        "--output-json",
                        str(acceptance_output),
                    ],
                    cwd=RAG_MCP_DIR,
                    env=python_env(),
                ),
                runner,
            )
        )

    if args.skip_java_tests:
        steps.append(skipped_step("java_bridge_tests"))
    else:
        steps.append(
            run_step(
                StepSpec(
                    name="java_bridge_tests",
                    command=[
                        maven_wrapper(),
                        "-q",
                        f"-Dtest={args.java_test_expression}",
                        "test",
                    ],
                    cwd=JCHATMIND_DIR,
                ),
                runner,
            )
        )

    status = "passed" if all(step["status"] != "failed" for step in steps) else "failed"
    report = {
        "status": status,
        "version": "2.3",
        "repo_root": str(REPO_ROOT),
        "steps": steps,
    }

    if args.report_json is not None:
        report_path = resolve_repo_path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the JChatMind RAG canary verification gate.")
    parser.add_argument("--skip-python-tests", action="store_true")
    parser.add_argument("--skip-acceptance", action="store_true")
    parser.add_argument("--skip-java-tests", action="store_true")
    parser.add_argument("--acceptance-rounds", type=int, default=3)
    parser.add_argument("--acceptance-output-json", type=Path, default=DEFAULT_ACCEPTANCE_OUTPUT)
    parser.add_argument("--java-test-expression", default=DEFAULT_JAVA_TEST_EXPRESSION)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)

    report = run_verification(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


def run_step(spec: StepSpec, runner: Runner = subprocess.run) -> dict[str, Any]:
    started = time.monotonic()
    completed = runner(
        spec.command,
        cwd=spec.cwd,
        env=spec.env,
        text=True,
        capture_output=True,
        check=False,
    )
    duration_ms = round((time.monotonic() - started) * 1000)
    return {
        "name": spec.name,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "duration_ms": duration_ms,
        "cwd": str(spec.cwd),
        "command": spec.command,
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
    }


def skipped_step(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
    }


def python_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_entries = [str(RAG_MCP_DIR)]
    deps_dir = RAG_MCP_DIR / ".deps"
    if deps_dir.exists():
        pythonpath_entries.insert(0, str(deps_dir))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def maven_wrapper() -> str:
    wrapper = "mvnw.cmd" if platform.system().lower().startswith("win") else "mvnw"
    return str(JCHATMIND_DIR / wrapper)


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def tail(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    return value[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
