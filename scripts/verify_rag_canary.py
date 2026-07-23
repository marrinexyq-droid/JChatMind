from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_MCP_DIR = REPO_ROOT / "rag-mcp"
JCHATMIND_DIR = REPO_ROOT / "jchatmind"
DEFAULT_JAVA_TEST_EXPRESSION = "!JChatMindV1Test,!JChatMindV2Test"
DEFAULT_ACCEPTANCE_OUTPUT = Path("rag-mcp/output/metrics/canary_acceptance_report.json")
DEFAULT_VERIFICATION_OUTPUT = Path("rag-mcp/output/metrics/rag_canary_verification.json")
DEFAULT_JAVA_BASELINE_REPORT = (
    RAG_MCP_DIR / "data" / "evaluation" / "java_current_pipeline_baseline.json"
)
STRICT_TEST_ENV_BLOCKLIST = {
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
}
SOURCE_ATTESTATION_VERSION = "source-tree-v1"
SOURCE_ATTESTATION_GROUPS = {
    "python_runtime": (
        "rag-mcp/main.py",
        "rag-mcp/src/**/*",
    ),
    "java_bridge": ("jchatmind/src/main/java/**/*",),
    "config": (
        "rag-mcp/config/**/*",
        "jchatmind/src/main/resources/**/*",
    ),
    "gates": (
        "scripts/**/*.py",
        "rag-mcp/scripts/**/*.py",
        ".github/workflows/**/*",
    ),
    "tests": (
        "rag-mcp/tests/**/*",
        "jchatmind/src/test/**/*",
        "pytest.ini",
        "rag-mcp/pytest.ini",
        "setup.cfg",
        "rag-mcp/setup.cfg",
        "tox.ini",
        "rag-mcp/tox.ini",
    ),
    "lockfiles": (
        "rag-mcp/pyproject.toml",
        "rag-mcp/uv.lock",
        "rag-mcp/requirements*.lock",
        "rag-mcp/requirements*.txt",
        "jchatmind/pom.xml",
        "jchatmind/mvnw",
        "jchatmind/mvnw.cmd",
        "jchatmind/.mvn/**/*",
    ),
    "evaluation_data": ("rag-mcp/data/evaluation/**/*",),
}
SOURCE_ATTESTATION_EXCLUDES = {
    "rag-mcp/data/evaluation/java_current_pipeline_baseline.json",
}
SOURCE_ATTESTATION_IGNORED_PARTS = {
    ".deps",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "output",
    "target",
}
SOURCE_ATTESTATION_IGNORED_SUFFIXES = {".pyc", ".pyo"}


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class StepSpec:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None


def run_verification(args: argparse.Namespace, runner: Runner = subprocess.run) -> dict[str, Any]:
    if args.acceptance_rounds < 1:
        raise ValueError("acceptance_rounds must be at least 1")

    report_path = (
        resolve_repo_path(args.report_json)
        if args.report_json is not None
        else None
    )
    if report_path is not None:
        report_path.unlink(missing_ok=True)
        atomic_temp_path(report_path).unlink(missing_ok=True)

    steps: list[dict[str, Any]] = []
    strict_cutover = bool(getattr(args, "strict_cutover", False))
    source_attestation_before: dict[str, Any] | None = None
    source_attestation_error: str | None = None
    if strict_cutover:
        try:
            source_attestation_before = build_source_attestation(REPO_ROOT)
        except OSError as exc:
            source_attestation_error = f"{type(exc).__name__}: {exc}"
    burn_in = {
        "requested_rounds": args.acceptance_rounds if strict_cutover else 0,
        "completed_rounds": 0,
        "rounds": [],
    }

    if args.skip_python_tests:
        steps.append(skipped_step("python_tests"))
    else:
        steps.append(
            run_step(
                StepSpec(
                    name="python_tests",
                    command=[sys.executable, "-m", "pytest", "-q"],
                    cwd=RAG_MCP_DIR,
                    env=python_env(strict=strict_cutover),
                ),
                runner,
            )
        )

    if args.skip_acceptance:
        steps.append(skipped_step("canary_acceptance"))
    elif strict_cutover:
        acceptance_output = resolve_repo_path(args.acceptance_output_json)
        for round_number in range(1, args.acceptance_rounds + 1):
            round_output = acceptance_round_path(acceptance_output, round_number)
            round_output.unlink(missing_ok=True)
            step = run_step(
                StepSpec(
                    name=f"canary_acceptance_round_{round_number}",
                    command=[
                        sys.executable,
                        "scripts/canary_acceptance.py",
                        "--ragas-rounds",
                        "1",
                        "--require-chroma",
                        "--current-pipeline",
                        "--answer-policy",
                        "generated",
                        "--java-baseline-report",
                        str(DEFAULT_JAVA_BASELINE_REPORT),
                        "--output-json",
                        str(round_output),
                    ],
                    cwd=RAG_MCP_DIR,
                    env=python_env(strict=True),
                ),
                runner,
            )
            steps.append(step)
            try:
                round_report = load_strict_json(round_output)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                round_report = None
                step["status"] = "failed"
                step["artifact_error"] = f"{type(exc).__name__}: {exc}"
            else:
                if not isinstance(round_report, dict):
                    step["status"] = "failed"
                    step["artifact_error"] = "round report must be a JSON object"
                elif round_report.get("status") != "passed":
                    step["status"] = "failed"
                    step["artifact_error"] = (
                        "round report status must be 'passed'"
                    )
                elif step["status"] == "passed":
                    burn_in["completed_rounds"] += 1
            burn_in["rounds"].append(
                {
                    "round": round_number,
                    "step_status": step["status"],
                    "report_path": str(round_output),
                    "report": round_report,
                }
            )
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
                        f"-Dtest={strict_java_test_expression(args, strict_cutover)}",
                        "test",
                    ],
                    cwd=JCHATMIND_DIR,
                    env=strict_test_env() if strict_cutover else None,
                ),
                runner,
            )
        )

    burn_in_complete = (
        not strict_cutover
        or (
            burn_in["requested_rounds"] == 3
            and burn_in["completed_rounds"] == burn_in["requested_rounds"]
            and len(burn_in["rounds"]) == burn_in["requested_rounds"]
        )
    )
    required_test_steps_complete = (
        not strict_cutover
        or all(
            any(
                step.get("name") == required_name
                and step.get("status") == "passed"
                for step in steps
            )
            for required_name in ("python_tests", "java_bridge_tests")
        )
    )
    source_attestation: dict[str, Any] | None = None
    if strict_cutover:
        try:
            source_attestation = build_source_attestation(REPO_ROOT)
        except OSError as exc:
            source_attestation_error = f"{type(exc).__name__}: {exc}"
    source_attestation_stable = (
        source_attestation_before is not None
        and source_attestation is not None
        and source_attestation_before == source_attestation
    )
    status = (
        "passed"
        if (
            burn_in_complete
            and required_test_steps_complete
            and (not strict_cutover or source_attestation_stable)
            and all(step["status"] != "failed" for step in steps)
        )
        else "failed"
    )
    report = {
        "status": status,
        "version": "3.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "strict_cutover": strict_cutover,
        "repo_root": str(REPO_ROOT),
        "steps": steps,
        "burn_in": burn_in,
        "source_attestation": source_attestation,
        "source_attestation_stable": (
            source_attestation_stable if strict_cutover else None
        ),
        "source_attestation_error": source_attestation_error,
    }

    if report_path is not None:
        serialized_report = dump_strict_json(report) + "\n"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = atomic_temp_path(report_path)
        temp_path.write_text(
            serialized_report,
            encoding="utf-8",
        )
        os.replace(temp_path, report_path)

    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the JChatMind RAG canary verification gate.")
    parser.add_argument("--skip-python-tests", action="store_true")
    parser.add_argument("--skip-acceptance", action="store_true")
    parser.add_argument("--skip-java-tests", action="store_true")
    parser.add_argument("--acceptance-rounds", type=positive_int, default=3)
    parser.add_argument("--acceptance-output-json", type=Path, default=DEFAULT_ACCEPTANCE_OUTPUT)
    parser.add_argument("--java-test-expression", default=DEFAULT_JAVA_TEST_EXPRESSION)
    parser.add_argument("--strict-cutover", action="store_true")
    parser.add_argument("--report-json", type=Path, default=DEFAULT_VERIFICATION_OUTPUT)
    args = parser.parse_args(argv)

    report = run_verification(args)
    print(dump_strict_json(report))
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


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def skipped_step(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
    }


def python_env(*, strict: bool = False) -> dict[str, str]:
    env = strict_test_env() if strict else os.environ.copy()
    pythonpath_entries = [str(RAG_MCP_DIR)]
    deps_dir = RAG_MCP_DIR / ".deps"
    if deps_dir.exists():
        pythonpath_entries.insert(0, str(deps_dir))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def strict_test_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in STRICT_TEST_ENV_BLOCKLIST:
        env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def build_source_attestation(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    group_summaries: dict[str, dict[str, Any]] = {}
    all_paths: set[str] = set()
    for group_name, patterns in SOURCE_ATTESTATION_GROUPS.items():
        matched: dict[str, Path] = {}
        for pattern in patterns:
            for candidate in root.glob(pattern):
                if not candidate.is_file():
                    continue
                relative_path = candidate.relative_to(root).as_posix()
                if relative_path in SOURCE_ATTESTATION_EXCLUDES:
                    continue
                if (
                    SOURCE_ATTESTATION_IGNORED_PARTS.intersection(
                        candidate.relative_to(root).parts
                    )
                    or candidate.suffix.lower()
                    in SOURCE_ATTESTATION_IGNORED_SUFFIXES
                ):
                    continue
                try:
                    candidate.resolve().relative_to(root)
                except ValueError:
                    continue
                matched[relative_path] = candidate

        file_records = []
        for relative_path in sorted(matched):
            normalized_content = normalize_attested_content(
                matched[relative_path].read_bytes()
            )
            file_records.append(
                {
                    "path": relative_path,
                    "sha256": hashlib.sha256(normalized_content).hexdigest(),
                }
            )
            all_paths.add(relative_path)

        group_payload = {
            "name": group_name,
            "patterns": list(patterns),
            "files": file_records,
        }
        group_summaries[group_name] = {
            "patterns": list(patterns),
            "file_count": len(file_records),
            "sha256": canonical_sha256(group_payload),
        }

    attestation_payload = {
        "version": SOURCE_ATTESTATION_VERSION,
        "excluded_paths": sorted(SOURCE_ATTESTATION_EXCLUDES),
        "groups": group_summaries,
    }
    return {
        **attestation_payload,
        "file_count": len(all_paths),
        "sha256": canonical_sha256(attestation_payload),
    }


def normalize_attested_content(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def maven_wrapper() -> str:
    wrapper = "mvnw.cmd" if platform.system().lower().startswith("win") else "mvnw"
    return str(JCHATMIND_DIR / wrapper)


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def acceptance_round_path(base_path: Path, round_number: int) -> Path:
    suffix = base_path.suffix or ".json"
    return base_path.with_name(f"{base_path.stem}.round-{round_number}{suffix}")


def strict_java_test_expression(args: argparse.Namespace, strict_cutover: bool) -> str:
    return (
        DEFAULT_JAVA_TEST_EXPRESSION
        if strict_cutover
        else args.java_test_expression
    )


def atomic_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp")


def load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_non_finite_json,
        parse_float=parse_finite_json_float,
    )


def reject_non_finite_json(value: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def dump_strict_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


def parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number is forbidden: {value}")
    return parsed


def tail(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    return value[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
