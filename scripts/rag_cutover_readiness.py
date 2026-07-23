from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.0"
VERIFICATION_REPORT_PATH = Path(
    "rag-mcp/output/metrics/rag_canary_verification.json"
)
VERIFICATION_REPORT_VERSION = "3.0"
ACCEPTANCE_REPORT_VERSION = "2.8"
PIPELINE_REPORT_VERSION = "1.1"
JUDGE_REPORT_VERSION = "2.5"
MAX_VERIFICATION_AGE_SECONDS = 24 * 60 * 60
STRICT_ROUNDS = 3
DEFAULT_JAVA_TEST_EXPRESSION = "!JChatMindV1Test,!JChatMindV2Test"
STRICT_EVIDENCE_DIR = Path("rag-mcp/output/metrics")
DEFAULT_JAVA_BASELINE_REPORT = Path(
    "rag-mcp/data/evaluation/java_current_pipeline_baseline.json"
)
JAVA_BASELINE_PRODUCER = "jchatmind-java-current-pipeline-evaluator"
JAVA_BASELINE_RUNTIME_SCOPE = "java_rag_retrieval"
JAVA_BASELINE_PRODUCER_PATH = Path("scripts/generate_java_rag_baseline.py")
GOLDEN_DATASET_PATH = Path(
    "rag-mcp/data/evaluation/ragas_cases.combined.jsonl"
)
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
COHORT_FINGERPRINT_VERSION = "pipeline-golden-v1"
RETRIEVAL_EVALUATOR_CONTRACT = {
    "name": "jchatmind-stable-context-retrieval",
    "version": "1.0",
    "match_basis": "ground_truth_context_ids",
    "recall_at_1": "matched_ground_truth_ids_at_rank_1/ground_truth_context_ids",
    "mrr": "reciprocal_rank_of_first_matched_ground_truth_context_id",
}
MATCH_METADATA_FIELDS = {
    "golden_context_id",
    "context_id",
    "source_path",
    "title",
    "heading",
}
JUDGE_THRESHOLDS = {
    "min_mean_faithfulness": 0.7,
    "min_mean_answer_relevancy": 0.7,
    "min_case_score": 0.5,
}
REQUIRED_STRICT_GATES = {
    "canary_smoke",
    "ragas_rounds_stable",
    "ragas_total_cases",
    "target_metric_present",
    "chroma_vector_store_runtime",
    "target_mrr",
    "target_precision_at_1",
    "current_pipeline_report_passed",
    "current_pipeline_executed",
    "current_pipeline_generated_answers",
    "current_pipeline_cases_present",
    "current_pipeline_no_case_errors",
    "current_pipeline_nonempty_answers",
    "current_pipeline_no_reference_fallback",
    "current_pipeline_chroma_backend",
    "current_pipeline_recall_at_1",
    "current_pipeline_mrr",
    "current_pipeline_judged_answers",
    "current_pipeline_java_baseline_comparable",
    "current_pipeline_recall_at_1_degradation",
    "current_pipeline_mrr_degradation",
    "current_pipeline_p95_latency",
    "current_pipeline_fallback_rate",
    "current_pipeline_error_rate",
}
JAVA_NON_CODE_PATTERN = re.compile(
    r'//[^\r\n]*|/\*.*?\*/|""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.DOTALL,
)


def evaluate_readiness(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    checks = [
        check_required_files(
            repo_root,
            "python_rag_subsystem_present",
            [
                "rag-mcp/pyproject.toml",
                "rag-mcp/main.py",
                "rag-mcp/src/core/query_engine.py",
                "rag-mcp/src/ingestion/pipeline.py",
                "rag-mcp/src/mcp_server/server.py",
                "rag-mcp/src/observability/trace_context.py",
                "rag-mcp/scripts/ingest.py",
                "rag-mcp/scripts/query.py",
            ],
            "Restore the Python RAG subsystem files before cutover.",
        ),
        check_required_files(
            repo_root,
            "canary_and_ci_gates_present",
            [
                "rag-mcp/scripts/canary_acceptance.py",
                "scripts/verify_rag_canary.py",
                ".github/workflows/rag-canary-acceptance.yml",
            ],
            "Keep the canary acceptance and CI verification gates in place.",
        ),
        check_required_files(
            repo_root,
            "java_baseline_producer_present",
            [JAVA_BASELINE_PRODUCER_PATH.as_posix()],
            (
                "Implement the fixed Task 9B Java baseline producer and bind its "
                "exact execution/artifact to strict verification before cutover."
            ),
        ),
        check_current_pipeline_gate(repo_root),
        check_default_bridge_enabled(repo_root),
        check_canary_profile(repo_root),
        check_java_rag_retired(repo_root),
        check_chroma_canonical(repo_root),
        check_llm_judged_ragas(repo_root),
        check_vision_adapter(repo_root),
    ]
    blockers = [check for check in checks if check["status"] == "blocked"]
    warnings = [check for check in checks if check["status"] == "warning"]
    return {
        "version": VERSION,
        "status": "ready" if not blockers else "not_ready",
        "repo_root": str(repo_root),
        "summary": {
            "passed": sum(1 for check in checks if check["status"] == "passed"),
            "blocked": len(blockers),
            "warnings": len(warnings),
        },
        "blockers": [check["name"] for check in blockers],
        "warnings": [check["name"] for check in warnings],
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Report whether JChatMind RAG is ready for Python default cutover."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate_readiness(args.repo_root)
    serialized_report = serialize_json_report(report)
    if args.output_json is not None:
        output_json = args.output_json if args.output_json.is_absolute() else args.repo_root / args.output_json
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(serialized_report, encoding="utf-8")
    print(serialized_report, end="")
    return 0 if report["status"] == "ready" or args.allow_not_ready else 1


def check_required_files(
    repo_root: Path,
    name: str,
    relative_paths: list[str],
    next_action: str,
) -> dict[str, Any]:
    missing = [path for path in relative_paths if not (repo_root / path).exists()]
    return check(
        name=name,
        status="passed" if not missing else "blocked",
        evidence={
            "required": relative_paths,
            "missing": missing,
        },
        next_action=next_action,
    )


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
                relative = candidate.relative_to(root)
                relative_path = relative.as_posix()
                if relative_path in SOURCE_ATTESTATION_EXCLUDES:
                    continue
                if (
                    SOURCE_ATTESTATION_IGNORED_PARTS.intersection(relative.parts)
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


def check_current_pipeline_gate(repo_root: Path) -> dict[str, Any]:
    relative_path = VERIFICATION_REPORT_PATH.as_posix()
    report_path = repo_root / VERIFICATION_REPORT_PATH
    evidence: dict[str, Any] = {
        "file": relative_path,
        "required_verifier_version": VERIFICATION_REPORT_VERSION,
        "required_acceptance_version": ACCEPTANCE_REPORT_VERSION,
        "max_age_hours": 24,
        "required_rounds": 3,
        "required_gates": sorted(REQUIRED_STRICT_GATES),
    }
    errors: list[str] = []

    if not report_path.is_file():
        errors.append("verification report is missing")
        evidence["errors"] = errors
        return check(
            name="current_pipeline_gate_passed",
            status="blocked",
            evidence=evidence,
            next_action=(
                "Run the strict three-round canary verifier and keep its fresh "
                f"report at {relative_path}."
            ),
        )

    try:
        report = load_strict_json(report_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"verification report is not valid JSON: {type(exc).__name__}")
        evidence["errors"] = errors
        return check(
            name="current_pipeline_gate_passed",
            status="blocked",
            evidence=evidence,
            next_action=(
                "Regenerate the strict canary verification report as valid JSON."
            ),
        )

    if not isinstance(report, Mapping):
        errors.append("verification report root must be an object")
        evidence["errors"] = errors
        return check(
            name="current_pipeline_gate_passed",
            status="blocked",
            evidence=evidence,
            next_action="Regenerate the strict canary verification report.",
        )

    verifier_version = report.get("version")
    evidence["verifier_version"] = verifier_version
    if verifier_version != VERIFICATION_REPORT_VERSION:
        errors.append(
            f"verifier version must be {VERIFICATION_REPORT_VERSION}"
        )

    verification_status = report.get("status")
    evidence["verification_status"] = verification_status
    if verification_status != "passed":
        errors.append("verification status must be passed")

    strict_cutover = report.get("strict_cutover")
    evidence["strict_cutover"] = strict_cutover
    if strict_cutover is not True:
        errors.append("strict_cutover must be true")

    current_source_attestation: dict[str, Any] | None = None
    try:
        current_source_attestation = build_source_attestation(repo_root)
    except OSError as exc:
        errors.append(
            "source-tree attestation could not be recomputed: "
            f"{type(exc).__name__}: {exc}"
        )
    declared_source_attestation = report.get("source_attestation")
    evidence["source_attestation_stable"] = report.get(
        "source_attestation_stable"
    )
    evidence["declared_source_attestation_sha256"] = (
        declared_source_attestation.get("sha256")
        if isinstance(declared_source_attestation, Mapping)
        else None
    )
    evidence["current_source_attestation_sha256"] = (
        current_source_attestation.get("sha256")
        if current_source_attestation is not None
        else None
    )
    evidence["source_attestation_groups"] = (
        sorted(current_source_attestation["groups"])
        if current_source_attestation is not None
        else []
    )
    if report.get("source_attestation_stable") is not True:
        errors.append("source-tree attestation must be stable during verification")
    if not isinstance(declared_source_attestation, Mapping):
        errors.append("source-tree attestation must be present in the report")
    elif (
        current_source_attestation is not None
        and dict(declared_source_attestation) != current_source_attestation
    ):
        errors.append(
            "source-tree attestation must match the current runtime, bridge, "
            "config, gates, tests, lockfiles, and evaluation data"
        )

    steps = report.get("steps")
    evidence["required_test_steps"] = ["python_tests", "java_bridge_tests"]
    step_rows: list[Mapping[str, Any]] = []
    if not isinstance(steps, list):
        errors.append("steps must be a list")
    else:
        step_rows = [mapping_value(raw_step) for raw_step in steps]
        expected_step_names = [
            "python_tests",
            *[
                f"canary_acceptance_round_{round_number}"
                for round_number in range(1, STRICT_ROUNDS + 1)
            ],
            "java_bridge_tests",
        ]
        step_names = [step.get("name") for step in step_rows]
        evidence["step_names"] = step_names
        if step_names != expected_step_names:
            errors.append(
                "steps must contain exactly one full Python suite, three ordered "
                "acceptance rounds, and one full Java bridge suite"
            )
        step_statuses = {
            str(step.get("name")): step.get("status")
            for step in step_rows
            if isinstance(step.get("name"), str)
        }
        evidence["test_step_statuses"] = {
            name: step_statuses.get(name)
            for name in ("python_tests", "java_bridge_tests")
        }
        errors.extend(validate_verification_step_commands(step_rows, repo_root))

    generated_at = parse_utc_timestamp(report.get("generated_at"))
    evidence["generated_at"] = report.get("generated_at")
    if generated_at is None:
        errors.append("generated_at must be an ISO-8601 timestamp with timezone")
    else:
        age_seconds = (
            datetime.now(timezone.utc) - generated_at
        ).total_seconds()
        evidence["age_hours"] = round(age_seconds / 3600, 3)
        if age_seconds < 0:
            errors.append("generated_at must not be in the future")
        elif age_seconds > MAX_VERIFICATION_AGE_SECONDS:
            errors.append("verification report is older than 24 hours")

    burn_in = mapping_value(report.get("burn_in"))
    requested_rounds = burn_in.get("requested_rounds")
    completed_rounds = burn_in.get("completed_rounds")
    rounds = burn_in.get("rounds")
    evidence["requested_rounds"] = requested_rounds
    evidence["completed_rounds"] = completed_rounds
    evidence["observed_rounds"] = len(rounds) if isinstance(rounds, list) else 0
    valid_requested_rounds = (
        isinstance(requested_rounds, int)
        and not isinstance(requested_rounds, bool)
        and requested_rounds == STRICT_ROUNDS
    )
    if not valid_requested_rounds:
        errors.append("burn_in.requested_rounds must equal 3")
    if completed_rounds != requested_rounds:
        errors.append("burn_in.completed_rounds must equal requested_rounds")
    if not isinstance(rounds, list):
        errors.append("burn_in.rounds must be a list")
        rounds = []
    elif valid_requested_rounds and len(rounds) != requested_rounds:
        errors.append("burn_in.rounds must contain exactly every requested round")

    invalid_rounds = []
    observed_report_paths: set[Path] = set()
    for index, round_report in enumerate(rounds, start=1):
        acceptance_step = (
            step_rows[index]
            if len(step_rows) == STRICT_ROUNDS + 2 and index < len(step_rows) - 1
            else {}
        )
        invalid = validate_burn_in_round(
            round_report,
            index=index,
            repo_root=repo_root,
            acceptance_step=acceptance_step,
            observed_report_paths=observed_report_paths,
            expected_source_attestation_sha256=(
                current_source_attestation.get("sha256")
                if current_source_attestation is not None
                else None
            ),
        )
        if invalid:
            invalid_rounds.append(invalid)
    if invalid_rounds:
        errors.append("one or more burn-in rounds failed strict validation")
        evidence["invalid_rounds"] = invalid_rounds

    evidence["errors"] = errors
    return check(
        name="current_pipeline_gate_passed",
        status="passed" if not errors else "blocked",
        evidence=evidence,
        next_action=(
            "Run at least three fresh strict cutover rounds with Chroma, generated "
            "answers, a passing judge, and every quality/runtime gate passing."
        ),
    )


def validate_burn_in_round(
    round_report: Any,
    *,
    index: int,
    repo_root: Path,
    acceptance_step: Mapping[str, Any],
    observed_report_paths: set[Path],
    expected_source_attestation_sha256: str | None,
) -> dict[str, Any] | None:
    errors: list[str] = []
    row = mapping_value(round_report)
    if not row:
        return {
            "index": index,
            "errors": ["round must be an object"],
        }

    round_number = row.get("round")
    report_path = row.get("report_path")
    resolved_report_path: Path | None = None
    if not isinstance(report_path, str) or not report_path.strip():
        errors.append("report_path must be a non-empty string")
    else:
        resolved_report_path = resolve_evidence_path(repo_root, report_path)
        if resolved_report_path is None:
            errors.append("report_path must stay inside rag-mcp/output/metrics")
        elif resolved_report_path in observed_report_paths:
            errors.append("report_path must be unique across burn-in rounds")
        else:
            observed_report_paths.add(resolved_report_path)
    if round_number != index:
        errors.append(f"round must be sequential and equal {index}")
    if row.get("step_status") != "passed":
        errors.append("step_status must be passed")

    expected_step_name = f"canary_acceptance_round_{index}"
    if acceptance_step.get("name") != expected_step_name:
        errors.append(f"matching step {expected_step_name} is missing")
    elif acceptance_step.get("status") != "passed":
        errors.append(f"matching step {expected_step_name} must be passed")
    elif not acceptance_command_matches(
        acceptance_step.get("command"),
        resolved_report_path,
        repo_root,
    ):
        errors.append(f"matching step {expected_step_name} command is not strict")

    acceptance = mapping_value(row.get("report"))
    if not acceptance:
        errors.append("report must contain an acceptance report object")
    else:
        if acceptance.get("version") != ACCEPTANCE_REPORT_VERSION:
            errors.append(
                f"acceptance report version must be {ACCEPTANCE_REPORT_VERSION}"
            )
        if acceptance.get("status") != "passed":
            errors.append("acceptance report status must be passed")
        if (
            acceptance.get("release_gate_source")
            != "current_pipeline_and_runtime_smoke"
        ):
            errors.append(
                "release_gate_source must be current_pipeline_and_runtime_smoke"
            )
        if (
            nested_value(
                acceptance,
                "canary",
                "report",
                "vector_store",
                "actual_backend",
            )
            != "ChromaVectorStore"
        ):
            errors.append("runtime canary vector store must be ChromaVectorStore")
        if (
            nested_value(
                acceptance,
                "current_pipeline",
                "report",
                "vector_store_backend",
            )
            != "ChromaVectorStore"
        ):
            errors.append("current pipeline vector store must be ChromaVectorStore")
        if (
            nested_value(acceptance, "current_pipeline", "answer_policy")
            != "generated"
        ):
            errors.append("current pipeline answer policy must be generated")
        if (
            nested_value(
                acceptance,
                "current_pipeline",
                "judge_report",
                "status",
            )
            != "passed"
        ):
            errors.append("current pipeline judge status must be passed")
        baseline_source_attestation_sha256 = nested_value(
            acceptance,
            "current_pipeline",
            "java_baseline_report",
            "source_attestation_sha256",
        )
        if expected_source_attestation_sha256 is None:
            errors.append(
                "current source-tree attestation must be available for baseline "
                "provenance validation"
            )
        elif (
            baseline_source_attestation_sha256
            != expected_source_attestation_sha256
        ):
            errors.append(
                "Java baseline source_attestation_sha256 must match the current "
                "source-tree attestation"
            )

        gates = acceptance.get("gates")
        gate_names: set[str] = set()
        gates_by_name: dict[str, Mapping[str, Any]] = {}
        failed_gates: list[str] = []
        invalid_gate_entries = False
        if isinstance(gates, list):
            for gate_index, gate in enumerate(gates, start=1):
                gate_mapping = mapping_value(gate)
                name = gate_mapping.get("name")
                status = gate_mapping.get("status")
                if not isinstance(name, str) or not name:
                    invalid_gate_entries = True
                    failed_gates.append(f"gate[{gate_index}]")
                    continue
                if name in gate_names:
                    invalid_gate_entries = True
                    failed_gates.append(f"duplicate:{name}")
                gate_names.add(name)
                gates_by_name[name] = gate_mapping
                if status != "passed":
                    failed_gates.append(name)
        else:
            invalid_gate_entries = True
            failed_gates.append("gates")

        missing_gates = sorted(REQUIRED_STRICT_GATES - gate_names)
        if missing_gates:
            errors.append(
                "missing required strict gates: " + ", ".join(missing_gates)
            )
        if invalid_gate_entries:
            errors.append("gates must be a list of named gate objects")
        if failed_gates:
            errors.append(
                "all acceptance gates must pass: " + ", ".join(failed_gates)
            )
        errors.extend(
            validate_acceptance_payload(
                acceptance,
                gates_by_name=gates_by_name,
                repo_root=repo_root,
            )
        )

    if resolved_report_path is not None:
        try:
            artifact = load_strict_json(resolved_report_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(
                "round artifact is missing or invalid: " + type(exc).__name__
            )
        else:
            if artifact != acceptance:
                errors.append("round artifact must match the embedded acceptance report")

    if not errors:
        return None
    return {
        "index": index,
        "round": round_number,
        "report_path": report_path,
        "errors": errors,
    }


def check_default_bridge_enabled(repo_root: Path) -> dict[str, Any]:
    application_path = repo_root / "jchatmind/src/main/resources/application.yaml"
    application = read_yaml_mapping(application_path)
    python_bridge = nested_mapping(application, "rag", "python-bridge")
    expected = [
        "enabled",
        "ingestion-enabled",
        "readiness-gate-enabled",
        "canary-preflight-enabled",
        "canary-preflight-fail-on-error",
    ]
    missing = [
        f"{key}: true"
        for key in expected
        if python_bridge.get(key) is not True
    ]
    return check(
        name="default_profile_delegates_to_python",
        status="passed" if not missing else "blocked",
        evidence={
            "file": "jchatmind/src/main/resources/application.yaml",
            "missing_enabled_settings": missing,
        },
        next_action=(
            "After canary burn-in, enable the Python bridge, ingestion bridge, "
            "readiness gate, and canary preflight in the default Spring profile."
        ),
    )


def check_canary_profile(repo_root: Path) -> dict[str, Any]:
    canary_path = (
        repo_root
        / "jchatmind/src/main/resources/application-rag-canary.yaml"
    )
    canary = read_yaml_mapping(canary_path)
    python_bridge = nested_mapping(canary, "rag", "python-bridge")
    expected_true = [
        "enabled",
        "ingestion-enabled",
        "readiness-gate-enabled",
        "canary-preflight-enabled",
        "canary-preflight-fail-on-error",
        "fail-on-ingestion-error",
    ]
    missing = [
        f"{key}: true"
        for key in expected_true
        if python_bridge.get(key) is not True
    ]
    expected_false = ["fallback-on-error", "fallback-on-empty"]
    missing.extend(
        f"{key}: false"
        for key in expected_false
        if python_bridge.get(key) is not False
    )
    profile = nested_value(canary, "spring", "config", "activate", "on-profile")
    if profile != "rag-canary":
        missing.append("on-profile: rag-canary")
    return check(
        name="rag_canary_profile_is_fail_fast",
        status="passed" if not missing else "blocked",
        evidence={
            "file": "jchatmind/src/main/resources/application-rag-canary.yaml",
            "missing_settings": missing,
        },
        next_action="Keep rag-canary as the fail-fast bridge profile before default cutover.",
    )


def check_java_rag_retired(repo_root: Path) -> dict[str, Any]:
    legacy_files = [
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java",
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/GraphRagServiceImpl.java",
    ]
    present = [path for path in legacy_files if (repo_root / path).exists()]
    deprecated_files = [
        path
        for path in present
        if java_class_is_deprecated_for_removal(
            read_text(repo_root / path),
            Path(path).stem,
        )
    ]
    deprecated = len(deprecated_files) == len(present)
    status = "passed" if not present or deprecated else "blocked"
    return check(
        name="java_rag_internals_retired_or_deprecated",
        status=status,
        evidence={
            "present_legacy_files": present,
            "deprecated_files": deprecated_files,
            "deprecated_marker_found": deprecated,
        },
        next_action=(
            "Deprecate, archive, or remove Java retrieval internals after the "
            "Python path becomes default and canary metrics stay stable."
        ),
    )


def validate_verification_step_commands(
    steps: list[Mapping[str, Any]],
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    for step in steps:
        name = step.get("name")
        if step.get("status") != "passed":
            errors.append(f"verification step {name or '<unnamed>'} must be passed")
        returncode = step.get("returncode")
        if (
            not isinstance(returncode, int)
            or isinstance(returncode, bool)
            or returncode != 0
        ):
            errors.append(
                f"verification step {name or '<unnamed>'} returncode must be 0"
            )
        expected_cwd = expected_step_cwd(repo_root, name)
        if (
            expected_cwd is not None
            and resolve_recorded_path(repo_root, step.get("cwd"))
            != expected_cwd
        ):
            errors.append(
                f"verification step {name or '<unnamed>'} cwd must be "
                f"{expected_cwd}"
            )

    python_steps = [step for step in steps if step.get("name") == "python_tests"]
    if len(python_steps) == 1:
        command = python_steps[0].get("command")
        if not command_matches(
            command,
            expected_executable=Path(sys.executable),
            expected_tail=["-m", "pytest", "-q"],
            repo_root=repo_root,
        ):
            errors.append(
                "python_tests command must use the current Python executable "
                "and run the full pytest suite"
            )

    java_steps = [step for step in steps if step.get("name") == "java_bridge_tests"]
    if len(java_steps) == 1:
        command = java_steps[0].get("command")
        if not command_matches(
            command,
            expected_executable=expected_maven_wrapper(repo_root),
            expected_tail=[
                "-q",
                f"-Dtest={DEFAULT_JAVA_TEST_EXPRESSION}",
                "test",
            ],
            repo_root=repo_root,
        ):
            errors.append(
                "java_bridge_tests command must use the repository Maven wrapper "
                "and the full fixed test expression"
            )
    return errors


def validate_acceptance_payload(
    acceptance: Mapping[str, Any],
    *,
    gates_by_name: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    golden_cohort, golden_errors = load_golden_cohort(repo_root)
    errors.extend(golden_errors)

    current = nested_mapping(acceptance, "current_pipeline")
    pipeline = nested_mapping(current, "report")
    dataset = nested_mapping(pipeline, "dataset")
    summary = nested_mapping(pipeline, "summary")
    retrieval = nested_mapping(pipeline, "retrieval_metrics")
    runtime = nested_mapping(pipeline, "runtime_metrics")

    if pipeline.get("version") != PIPELINE_REPORT_VERSION:
        errors.append(
            f"current pipeline report version must be {PIPELINE_REPORT_VERSION}"
        )
    if pipeline.get("status") != "passed":
        errors.append("current pipeline report status must be passed")
    if pipeline.get("mode") != "hybrid":
        errors.append("current pipeline mode must be hybrid")
    if pipeline.get("runtime_scope") != "python_query_engine":
        errors.append("current pipeline runtime scope must be explicit")
    pipeline_evidence, pipeline_errors = recompute_report_evidence(
        pipeline,
        golden_cohort,
        label="current pipeline",
        require_runtime=True,
    )
    errors.extend(pipeline_errors)

    recall = evidence_value(pipeline_evidence, "recall_at_1")
    mrr = evidence_value(pipeline_evidence, "mrr")
    p95 = evidence_value(pipeline_evidence, "p95_latency_ms")
    fallback_rate = evidence_value(pipeline_evidence, "fallback_rate")
    error_rate = evidence_value(pipeline_evidence, "error_rate")
    case_count = evidence_value(pipeline_evidence, "case_count")
    if pipeline_evidence is not None:
        expected_dataset = golden_cohort["dataset"] if golden_cohort else None
        if dataset != expected_dataset:
            errors.append(
                "current pipeline dataset must match the local Golden semantic cohort"
            )
        if summary.get("case_count") != pipeline_evidence["case_count"]:
            errors.append(
                "current pipeline summary case_count must match recomputed cases"
            )
        if summary.get("error_count") != pipeline_evidence["error_count"]:
            errors.append(
                "current pipeline summary error_count must match recomputed cases"
            )
        if (
            summary.get("empty_answer_count")
            != pipeline_evidence["empty_answer_count"]
        ):
            errors.append(
                "current pipeline summary empty_answer_count must match recomputed cases"
            )
        if pipeline.get("status") != pipeline_evidence["status"]:
            errors.append(
                "current pipeline status must match recomputed case outcomes"
            )
        if pipeline_evidence["error_count"] != 0:
            errors.append("current pipeline cases must contain no errors")
        if pipeline_evidence["empty_answer_count"] != 0:
            errors.append("current pipeline cases must contain no empty answers")
        if pipeline_evidence["fallback_count"] != 0:
            errors.append(
                "every current pipeline case must use a generated answer"
            )
        if pipeline_evidence["reference_fallback_count"] != 0:
            errors.append(
                "current pipeline cases must contain no reference fallback"
            )
        if not metric_values_match(
            retrieval,
            pipeline_evidence,
            ("recall_at_1", "mrr"),
        ):
            errors.append(
                "current pipeline retrieval metrics must match per-case recomputation"
            )
        if not metric_values_match(
            runtime,
            pipeline_evidence,
            ("p95_latency_ms", "fallback_rate", "error_rate"),
        ):
            errors.append(
                "current pipeline runtime metrics must match per-case recomputation"
            )

    if not is_probability(recall) or recall < 0.9:
        errors.append("current pipeline Recall@1 must be finite and at least 0.9")
    if not is_probability(mrr) or mrr < 0.95:
        errors.append("current pipeline MRR must be finite and at least 0.95")
    if not is_finite_number(p95) or p95 < 0 or p95 > 8000.0:
        errors.append("current pipeline P95 must be finite and at most 8000 ms")
    if not is_probability(fallback_rate) or fallback_rate > 0.01:
        errors.append("current pipeline fallback rate must be at most 0.01")
    if not is_probability(error_rate) or error_rate > 0.01:
        errors.append("current pipeline error rate must be at most 0.01")

    baseline = nested_mapping(current, "java_baseline_report")
    baseline_dataset = nested_mapping(baseline, "dataset")
    baseline_retrieval = nested_mapping(baseline, "retrieval_metrics")
    baseline_evidence, baseline_errors = recompute_report_evidence(
        baseline,
        golden_cohort,
        label="Java baseline",
        require_runtime=False,
    )
    errors.extend(baseline_errors)
    baseline_recall = evidence_value(baseline_evidence, "recall_at_1")
    baseline_mrr = evidence_value(baseline_evidence, "mrr")
    if current.get("java_baseline_required") is not True:
        errors.append("comparable Java baseline must be required")
    if current.get("java_baseline_error") not in (None, ""):
        errors.append("Java baseline report must load without error")
    if baseline.get("version") != PIPELINE_REPORT_VERSION:
        errors.append(
            f"Java baseline report version must be {PIPELINE_REPORT_VERSION}"
        )
    if baseline.get("producer") != JAVA_BASELINE_PRODUCER:
        errors.append(
            f"Java baseline producer must be {JAVA_BASELINE_PRODUCER}"
        )
    if baseline.get("runtime_scope") != JAVA_BASELINE_RUNTIME_SCOPE:
        errors.append(
            "Java baseline runtime_scope must be "
            f"{JAVA_BASELINE_RUNTIME_SCOPE}"
        )
    baseline_generated_at = parse_utc_timestamp(
        baseline.get("generated_at")
    )
    if baseline_generated_at is None:
        errors.append(
            "Java baseline generated_at must be an ISO-8601 timestamp "
            "with timezone"
        )
    elif baseline_generated_at > datetime.now(timezone.utc):
        errors.append("Java baseline generated_at must not be in the future")
    if (
        baseline.get("status") != "passed"
        or baseline.get("mode") != pipeline.get("mode")
        or baseline_dataset != dataset
        or baseline.get("top_k") != pipeline.get("top_k")
        or baseline.get("evaluator") != RETRIEVAL_EVALUATOR_CONTRACT
        or pipeline.get("evaluator") != RETRIEVAL_EVALUATOR_CONTRACT
        or baseline_evidence is None
        or pipeline_evidence is None
    ):
        errors.append(
            "Java baseline must use the same semantic cohort, mode, top_k, "
            "and evaluator contract"
        )
    else:
        if not metric_values_match(
            baseline_retrieval,
            baseline_evidence,
            ("recall_at_1", "mrr"),
        ):
            errors.append(
                "Java baseline retrieval metrics must match per-case recomputation"
            )
        if is_probability(recall) and recall < baseline_recall - 0.02:
            errors.append("current pipeline Recall@1 degradation exceeds 0.02")
        if is_probability(mrr) and mrr < baseline_mrr - 0.02:
            errors.append("current pipeline MRR degradation exceeds 0.02")

    baseline_path = repo_root / DEFAULT_JAVA_BASELINE_REPORT
    try:
        baseline_artifact = load_strict_json(baseline_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append("Java baseline artifact is missing or invalid: " + type(exc).__name__)
    else:
        if baseline_artifact != baseline:
            errors.append("Java baseline artifact must match the embedded baseline")

    judge = nested_mapping(current, "judge_report")
    judge_metadata = nested_mapping(judge, "judge")
    judge_evidence, judge_errors = recompute_judge_evidence(
        judge,
        golden_cohort,
        pipeline_evidence,
    )
    errors.extend(judge_errors)
    if (
        str(judge_metadata.get("provider") or "").lower()
        not in {"google", "gemini"}
        or not str(judge_metadata.get("model") or "").strip()
    ):
        errors.append("real Judge evidence must use a configured Gemini judge")
    if (
        judge_evidence is None
        or judge_evidence.get("status") != "passed"
        or judge_evidence.get("failed_cases") != []
        or judge_evidence.get("case_count") != case_count
    ):
        errors.append(
            "real Judge evidence must independently pass every current pipeline case"
        )

    expected_numeric_gates = {
        "current_pipeline_recall_at_1": (recall, 0.9),
        "current_pipeline_mrr": (mrr, 0.95),
        "current_pipeline_p95_latency": (p95, 8000.0),
        "current_pipeline_fallback_rate": (fallback_rate, 0.01),
        "current_pipeline_error_rate": (error_rate, 0.01),
    }
    for name, (observed, threshold) in expected_numeric_gates.items():
        gate = gates_by_name.get(name, {})
        if not numbers_equal(gate.get("observed"), observed) or not numbers_equal(
            gate.get("threshold"), threshold
        ):
            errors.append(f"{name} gate evidence does not match the pipeline report")

    degradation_gates = {
        "current_pipeline_recall_at_1_degradation": (recall, baseline_recall),
        "current_pipeline_mrr_degradation": (mrr, baseline_mrr),
    }
    for name, (observed, baseline_value) in degradation_gates.items():
        gate = gates_by_name.get(name, {})
        threshold = mapping_value(gate.get("threshold"))
        if (
            not numbers_equal(gate.get("observed"), observed)
            or not numbers_equal(threshold.get("baseline"), baseline_value)
            or not numbers_equal(threshold.get("max_degradation"), 0.02)
            or not numbers_equal(
                threshold.get("minimum"),
                baseline_value - 0.02 if is_probability(baseline_value) else None,
            )
        ):
            errors.append(f"{name} gate evidence does not match the Java baseline")
    return errors


def load_golden_cohort(
    repo_root: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = repo_root / GOLDEN_DATASET_PATH
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return None, [
            "local Golden dataset is missing or unreadable: "
            + type(exc).__name__
        ]

    semantic_cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    judge_values_by_id: dict[str, dict[str, str]] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(
                line,
                parse_constant=reject_non_finite_json,
                parse_float=parse_finite_float,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return None, [
                f"local Golden dataset line {line_number} is invalid: "
                f"{type(exc).__name__}"
            ]
        if not isinstance(raw, Mapping):
            return None, [
                f"local Golden dataset line {line_number} must be an object"
            ]
        if raw.get("dataset_split") != "answer_generation":
            continue
        try:
            semantic = semantic_golden_case(raw)
        except (TypeError, ValueError) as exc:
            return None, [
                f"local Golden case at line {line_number} is invalid: {exc}"
            ]
        case_id = semantic["case_id"]
        if case_id in seen_case_ids:
            return None, [f"local Golden dataset has duplicate case_id {case_id}"]
        seen_case_ids.add(case_id)
        semantic_cases.append(semantic)
        judge_values_by_id[case_id] = {
            "question": str(raw["question"]),
            "reference_answer": str(
                raw.get("reference_answer")
                or raw.get("ground_truth")
                or ""
            ),
        }

    if not semantic_cases:
        return None, [
            "local Golden dataset has no answer_generation cases"
        ]

    case_ids = [case["case_id"] for case in semantic_cases]
    dataset = {
        "case_count": len(semantic_cases),
        "case_ids_sha256": canonical_sha256(case_ids, sort_keys=False),
        "cohort_sha256": canonical_sha256(semantic_cases),
        "cohort_fingerprint_version": COHORT_FINGERPRINT_VERSION,
    }
    cases_by_id = {
        case["case_id"]: {
            "golden_case_sha256": canonical_sha256(case),
            "ground_truth_context_ids": case["ground_truth_context_ids"],
            "question": judge_values_by_id[case["case_id"]]["question"],
            "reference_answer": judge_values_by_id[case["case_id"]][
                "reference_answer"
            ],
            "source_refs": case["source_refs"],
            "reference_contexts": case["reference_contexts"],
        }
        for case in semantic_cases
    }
    return {
        "dataset": dataset,
        "case_ids": case_ids,
        "cases_by_id": cases_by_id,
    }, []


def semantic_golden_case(raw: Mapping[str, Any]) -> dict[str, Any]:
    case_id = raw.get("case_id")
    question = raw.get("question")
    ground_truth = raw.get("ground_truth")
    reference_answer = raw.get("reference_answer")
    ground_truth_ids = raw.get("ground_truth_context_ids")
    source_refs = raw.get("source_refs")
    reference_contexts = raw.get("reference_contexts")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if not isinstance(ground_truth, str) or not ground_truth.strip():
        raise ValueError("ground_truth must be a non-empty string")
    if reference_answer is not None and not isinstance(reference_answer, str):
        raise ValueError("reference_answer must be a string when present")
    if (
        not isinstance(ground_truth_ids, list)
        or not ground_truth_ids
        or not all(
            isinstance(context_id, str) and context_id.strip()
            for context_id in ground_truth_ids
        )
    ):
        raise ValueError(
            "ground_truth_context_ids must be a non-empty string list"
        )
    normalized_truth_ids = normalize_semantic_value(ground_truth_ids)
    if len(set(normalized_truth_ids)) != len(normalized_truth_ids):
        raise ValueError("ground_truth_context_ids must be unique")
    if not isinstance(source_refs, list) or not all(
        isinstance(source_ref, Mapping) for source_ref in source_refs
    ):
        raise ValueError("source_refs must be an object list")
    if not isinstance(reference_contexts, list) or not all(
        isinstance(context, str) for context in reference_contexts
    ):
        raise ValueError("reference_contexts must be a string list")
    return {
        "case_id": case_id.strip(),
        "question": question.strip(),
        "ground_truth_context_ids": normalized_truth_ids,
        "source_refs": normalize_semantic_value(source_refs),
        "reference_contexts": normalize_semantic_value(reference_contexts),
        "ground_truth": ground_truth.strip(),
        "reference_answer": (
            reference_answer or ground_truth
        ).strip(),
    }


def normalize_semantic_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return {
            str(key): normalize_semantic_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_semantic_value(item) for item in value]
    return value


def canonical_sha256(value: Any, *, sort_keys: bool = True) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def match_ground_truth_context(
    result: Mapping[str, Any],
    golden_case: Mapping[str, Any],
) -> str | None:
    truth_ids = golden_case["ground_truth_context_ids"]
    chunk_id = str(result["chunk_id"])
    if chunk_id in truth_ids:
        return chunk_id

    metadata = mapping_value(result.get("metadata"))
    metadata_context_id = str(
        metadata.get("golden_context_id")
        or metadata.get("context_id")
        or ""
    )
    if metadata_context_id in truth_ids:
        return metadata_context_id

    result_source_path = str(metadata.get("source_path") or "")
    result_heading = str(
        metadata.get("title") or metadata.get("heading") or ""
    )
    for source_ref in golden_case["source_refs"]:
        context_id = str(source_ref.get("context_id") or "")
        if context_id not in truth_ids:
            continue
        expected_path = str(source_ref.get("source_path") or "")
        expected_heading = str(source_ref.get("heading") or "")
        if (
            expected_path
            and source_path_matches(result_source_path, expected_path)
            and (
                not expected_heading
                or normalized_match_text(result_heading)
                == normalized_match_text(expected_heading)
            )
        ):
            return context_id

    result_text = str(result["text"])
    for index, reference_context in enumerate(
        golden_case["reference_contexts"]
    ):
        if not context_text_matches(result_text, str(reference_context)):
            continue
        if index < len(truth_ids):
            return truth_ids[index]
        if len(truth_ids) == 1:
            return truth_ids[0]
    return None


def source_path_matches(actual: str, expected: str) -> bool:
    normalized_actual = actual.replace("\\", "/").lower().strip()
    normalized_expected = expected.replace("\\", "/").lower().strip()
    return bool(normalized_expected) and (
        normalized_actual == normalized_expected
        or normalized_actual.endswith(f"/{normalized_expected}")
    )


def context_text_matches(actual: str, expected: str) -> bool:
    normalized_actual = normalized_match_text(actual)
    normalized_expected = normalized_match_text(expected)
    if min(len(normalized_actual), len(normalized_expected)) < 24:
        return False
    return (
        normalized_actual in normalized_expected
        or normalized_expected in normalized_actual
    )


def normalized_match_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def recompute_report_evidence(
    report: Mapping[str, Any],
    golden_cohort: dict[str, Any] | None,
    *,
    label: str,
    require_runtime: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    if golden_cohort is None:
        return None, [f"{label} cannot be verified without local Golden data"]

    errors: list[str] = []
    dataset = nested_mapping(report, "dataset")
    if dataset != golden_cohort["dataset"]:
        errors.append(
            f"{label} dataset does not match the local Golden semantic cohort"
        )
    if report.get("evaluator") != RETRIEVAL_EVALUATOR_CONTRACT:
        errors.append(f"{label} evaluator contract is not the fixed contract")
    top_k = report.get("top_k")
    if not is_positive_int(top_k):
        errors.append(f"{label} top_k must be a positive integer")

    cases = report.get("cases")
    expected_case_ids = golden_cohort["case_ids"]
    if not isinstance(cases, list) or len(cases) != len(expected_case_ids):
        errors.append(f"{label} cases must cover the full local Golden cohort")
        return None, errors

    recall_values: list[float] = []
    mrr_values: list[float] = []
    latencies: list[float] = []
    error_count = 0
    empty_answer_count = 0
    fallback_count = 0
    reference_fallback_count = 0
    judge_input_sha256_by_case: dict[str, str] = {}
    for index, expected_case_id in enumerate(expected_case_ids):
        row = mapping_value(cases[index])
        local_case = golden_cohort["cases_by_id"][expected_case_id]
        required_fields = {
            "case_id",
            "golden_case_sha256",
            "ground_truth_context_ids",
            "matched_ground_truth_context_ids",
            "retrieved_results",
        }
        if require_runtime:
            required_fields.update(
                {
                    "retrieved_context_ids",
                    "retrieved_contexts",
                    "answer",
                    "answer_source",
                    "latency_ms",
                    "error",
                }
            )
        if not row or not required_fields.issubset(row):
            errors.append(
                f"{label} case {expected_case_id} is missing recomputation fields"
            )
            continue
        if row.get("case_id") != expected_case_id:
            errors.append(
                f"{label} case order/coverage does not match local Golden data"
            )
            continue
        if (
            row.get("golden_case_sha256")
            != local_case["golden_case_sha256"]
        ):
            errors.append(
                f"{label} case {expected_case_id} fingerprint is not local Golden"
            )
            continue
        truth_ids = row.get("ground_truth_context_ids")
        if truth_ids != local_case["ground_truth_context_ids"]:
            errors.append(
                f"{label} case {expected_case_id} ground truth IDs do not match"
            )
            continue
        retrieved_results = row.get("retrieved_results")
        if (
            not isinstance(retrieved_results, list)
            or not is_positive_int(top_k)
            or len(retrieved_results) > top_k
        ):
            errors.append(
                f"{label} case {expected_case_id} retrieved results are invalid"
            )
            continue
        normalized_results: list[Mapping[str, Any]] = []
        invalid_result = False
        for raw_result in retrieved_results:
            if not isinstance(raw_result, Mapping):
                invalid_result = True
                break
            chunk_id = raw_result.get("chunk_id")
            text = raw_result.get("text")
            metadata = raw_result.get("metadata")
            if (
                not isinstance(chunk_id, str)
                or not chunk_id.strip()
                or not isinstance(text, str)
                or not text.strip()
                or not isinstance(metadata, Mapping)
                or not set(metadata).issubset(MATCH_METADATA_FIELDS)
                or not all(
                    is_stable_metadata_scalar(value)
                    for value in metadata.values()
                )
            ):
                invalid_result = True
                break
            normalized_results.append(raw_result)
        if invalid_result:
            errors.append(
                f"{label} case {expected_case_id} retrieved results are invalid"
            )
            continue
        recomputed_matched_ids = [
            match_ground_truth_context(result, local_case)
            for result in normalized_results
        ]
        matched_ids = row.get("matched_ground_truth_context_ids")
        if (
            not isinstance(matched_ids, list)
            or matched_ids != recomputed_matched_ids
        ):
            errors.append(
                f"{label} case {expected_case_id} matched IDs do not match "
                "retrieved result evidence"
            )
            continue
        if require_runtime:
            retrieved_ids = row.get("retrieved_context_ids")
            retrieved_contexts = row.get("retrieved_contexts")
            evidence_ids = [
                str(result["chunk_id"]) for result in normalized_results
            ]
            evidence_contexts = [
                str(result["text"]) for result in normalized_results
            ]
            if (
                not isinstance(retrieved_ids, list)
                or retrieved_ids != evidence_ids
                or not isinstance(retrieved_contexts, list)
                or retrieved_contexts != evidence_contexts
            ):
                errors.append(
                    f"{label} case {expected_case_id} retrieved evidence is invalid"
                )
                continue
            latency = row.get("latency_ms")
            if not is_finite_number(latency) or latency < 0:
                errors.append(
                    f"{label} case {expected_case_id} latency is invalid"
                )
                continue
            error = row.get("error")
            answer = row.get("answer")
            answer_source = row.get("answer_source")
            if error is not None and not isinstance(error, str):
                errors.append(
                    f"{label} case {expected_case_id} error is invalid"
                )
                continue
            if not isinstance(answer, str) or not isinstance(answer_source, str):
                errors.append(
                    f"{label} case {expected_case_id} answer fields are invalid"
                )
                continue
            latencies.append(float(latency))
            error_count += error is not None
            empty_answer_count += not bool(answer.strip())
            fallback_count += answer_source != "generated_answer"
            reference_fallback_count += (
                answer_source == "reference_answer_fallback"
            )
            judge_input_sha256_by_case[expected_case_id] = (
                canonical_sha256(
                    {
                        "case_id": expected_case_id,
                        "question": local_case["question"],
                        "generated_answer": answer.strip(),
                        "retrieved_contexts": retrieved_contexts,
                        "reference_answer": local_case["reference_answer"],
                        "answer_source": answer_source,
                    }
                )
            )

        truth_set = set(truth_ids)
        first_match = (
            recomputed_matched_ids[0]
            if recomputed_matched_ids
            else None
        )
        recall_values.append(
            (1.0 / len(truth_ids)) if first_match in truth_set else 0.0
        )
        reciprocal_rank = 0.0
        for rank, context_id in enumerate(
            recomputed_matched_ids,
            start=1,
        ):
            if context_id is not None:
                reciprocal_rank = 1.0 / rank
                break
        mrr_values.append(reciprocal_rank)

    if errors:
        return None, errors

    case_count = len(expected_case_ids)
    evidence = {
        "case_count": case_count,
        "recall_at_1": round(sum(recall_values) / case_count, 4),
        "mrr": round(sum(mrr_values) / case_count, 4),
    }
    if require_runtime:
        sorted_latencies = sorted(latencies)
        percentile_index = max(0, ceil(0.95 * case_count) - 1)
        evidence.update(
            {
                "p95_latency_ms": round(
                    sorted_latencies[percentile_index],
                    3,
                ),
                "fallback_rate": round(fallback_count / case_count, 4),
                "error_rate": round(error_count / case_count, 4),
                "fallback_count": fallback_count,
                "reference_fallback_count": reference_fallback_count,
                "error_count": error_count,
                "empty_answer_count": empty_answer_count,
                "status": (
                    "passed"
                    if error_count == 0 and empty_answer_count == 0
                    else "failed"
                ),
                "judge_input_sha256_by_case": (
                    judge_input_sha256_by_case
                ),
            }
        )
    return evidence, []


def recompute_judge_evidence(
    judge: Mapping[str, Any],
    golden_cohort: dict[str, Any] | None,
    pipeline_evidence: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if golden_cohort is None:
        return None, ["Judge evidence cannot be verified without local Golden data"]
    if pipeline_evidence is None:
        return None, ["Judge evidence cannot be verified without pipeline cases"]

    errors: list[str] = []
    expected_case_ids = golden_cohort["case_ids"]
    if judge.get("version") != JUDGE_REPORT_VERSION:
        errors.append(
            f"Judge report version must be {JUDGE_REPORT_VERSION}"
        )
    if judge.get("thresholds") != JUDGE_THRESHOLDS:
        errors.append("Judge thresholds must match the fixed acceptance contract")
    cases = judge.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected_case_ids):
        errors.append("Judge cases must cover the full local Golden cohort")
        return None, errors

    faithfulness_values: list[float] = []
    relevancy_values: list[float] = []
    for index, expected_case_id in enumerate(expected_case_ids):
        row = mapping_value(cases[index])
        faithfulness = row.get("faithfulness")
        relevancy = row.get("answer_relevancy")
        expected_input_sha256 = pipeline_evidence[
            "judge_input_sha256_by_case"
        ][expected_case_id]
        if (
            not row
            or row.get("case_id") != expected_case_id
            or row.get("evaluation_input_sha256")
            != expected_input_sha256
            or row.get("answer_source") != "generated_answer"
            or not is_probability(faithfulness)
            or not is_probability(relevancy)
        ):
            errors.append(
                f"Judge case {expected_case_id} is missing valid scored coverage"
            )
            continue
        faithfulness_values.append(float(faithfulness))
        relevancy_values.append(float(relevancy))
    if errors:
        return None, errors

    faithfulness_summary = score_summary(faithfulness_values)
    relevancy_summary = score_summary(relevancy_values)
    failed_cases = [
        expected_case_ids[index]
        for index, (faithfulness, relevancy) in enumerate(
            zip(faithfulness_values, relevancy_values)
        )
        if faithfulness < JUDGE_THRESHOLDS["min_case_score"]
        or relevancy < JUDGE_THRESHOLDS["min_case_score"]
    ]
    status = (
        "passed"
        if (
            faithfulness_summary["mean"]
            >= JUDGE_THRESHOLDS["min_mean_faithfulness"]
            and relevancy_summary["mean"]
            >= JUDGE_THRESHOLDS["min_mean_answer_relevancy"]
            and not failed_cases
        )
        else "failed"
    )
    evidence = {
        "case_count": len(expected_case_ids),
        "metrics": {
            "faithfulness": faithfulness_summary,
            "answer_relevancy": relevancy_summary,
        },
        "failed_cases": failed_cases,
        "status": status,
    }
    if judge.get("case_count") != evidence["case_count"]:
        errors.append("Judge case_count must match recomputed case coverage")
    judge_metrics = nested_mapping(judge, "metrics")
    if not score_summary_matches(
        nested_mapping(judge_metrics, "faithfulness"),
        faithfulness_summary,
    ):
        errors.append("Judge faithfulness metrics must match case scores")
    if not score_summary_matches(
        nested_mapping(judge_metrics, "answer_relevancy"),
        relevancy_summary,
    ):
        errors.append("Judge answer relevancy metrics must match case scores")
    if judge.get("failed_cases") != failed_cases:
        errors.append("Judge failed_cases must match case score thresholds")
    if judge.get("status") != status:
        errors.append("Judge status must match recomputed metrics")
    return evidence, errors


def score_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": round(sum(values) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def score_summary_matches(
    declared: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> bool:
    return all(
        numbers_equal(declared.get(name), recomputed.get(name))
        for name in ("mean", "min", "max")
    )


def metric_values_match(
    declared: Mapping[str, Any],
    recomputed: Mapping[str, Any],
    names: tuple[str, ...],
) -> bool:
    return all(
        numbers_equal(declared.get(name), recomputed.get(name))
        for name in names
    )


def evidence_value(
    evidence: Mapping[str, Any] | None,
    name: str,
) -> Any:
    return evidence.get(name) if evidence is not None else None


def is_finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def is_probability(value: Any) -> bool:
    return is_finite_number(value) and 0.0 <= value <= 1.0


def is_stable_metadata_scalar(value: Any) -> bool:
    return (
        isinstance(value, (str, bool, int))
        or isinstance(value, float)
        and math.isfinite(value)
    )


def is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def numbers_equal(left: Any, right: Any) -> bool:
    return (
        is_finite_number(left)
        and is_finite_number(right)
        and abs(float(left) - float(right)) <= 1e-9
    )


def java_class_is_deprecated_for_removal(text: str, class_name: str) -> bool:
    source = JAVA_NON_CODE_PATTERN.sub(" ", text)
    class_pattern = re.compile(
        r"@Deprecated\s*\(\s*forRemoval\s*=\s*true\s*\)\s*"
        r"(?:@[A-Za-z_$][\w.$]*(?:\s*\([^()\r\n]*\))?\s*)*"
        r"(?:(?:public|protected|private|abstract|final|sealed|non-sealed|static)\s+)*"
        rf"class\s+{re.escape(class_name)}\b"
    )
    return class_pattern.search(source) is not None


def expected_step_cwd(repo_root: Path, name: Any) -> Path | None:
    if name == "python_tests" or (
        isinstance(name, str) and name.startswith("canary_acceptance_round_")
    ):
        return (repo_root / "rag-mcp").resolve()
    if name == "java_bridge_tests":
        return (repo_root / "jchatmind").resolve()
    return None


def expected_maven_wrapper(repo_root: Path) -> Path:
    wrapper = "mvnw.cmd" if sys.platform.startswith("win") else "mvnw"
    return (repo_root / "jchatmind" / wrapper).resolve()


def command_matches(
    command: Any,
    *,
    expected_executable: Path,
    expected_tail: list[str],
    repo_root: Path,
) -> bool:
    return (
        isinstance(command, list)
        and all(isinstance(part, str) for part in command)
        and len(command) == len(expected_tail) + 1
        and executable_matches(command[0], expected_executable, repo_root)
        and command[1:] == expected_tail
    )


def executable_matches(
    recorded: Any,
    expected: Path,
    repo_root: Path,
) -> bool:
    expected = expected.resolve()
    return (
        isinstance(recorded, str)
        and expected.is_file()
        and resolve_recorded_path(repo_root, recorded) == expected
    )


def acceptance_command_matches(
    command: Any,
    resolved_report_path: Path | None,
    repo_root: Path,
) -> bool:
    if resolved_report_path is None or not isinstance(command, list):
        return False
    if not all(isinstance(part, str) for part in command):
        return False
    if not executable_matches(command[0], Path(sys.executable), repo_root):
        return False
    expected_prefix = [
        "scripts/canary_acceptance.py",
        "--ragas-rounds",
        "1",
        "--require-chroma",
        "--current-pipeline",
        "--answer-policy",
        "generated",
        "--java-baseline-report",
    ]
    if (
        len(command) != len(expected_prefix) + 4
        or command[1:9] != expected_prefix
        or command[10] != "--output-json"
    ):
        return False
    baseline_path = resolve_repo_file(repo_root, command[9])
    expected_baseline_path = (repo_root / DEFAULT_JAVA_BASELINE_REPORT).resolve()
    command_report_path = resolve_evidence_path(repo_root, command[11])
    return (
        baseline_path == expected_baseline_path
        and command_report_path == resolved_report_path
    )


def resolve_repo_file(repo_root: Path, value: str) -> Path | None:
    try:
        candidate = Path(value)
        return (
            candidate.resolve()
            if candidate.is_absolute()
            else (repo_root / candidate).resolve()
        )
    except (OSError, ValueError):
        return None


def resolve_recorded_path(repo_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return resolve_repo_file(repo_root, value)


def resolve_evidence_path(repo_root: Path, value: str) -> Path | None:
    try:
        candidate = Path(value)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (repo_root / candidate).resolve()
        )
        evidence_root = (repo_root / STRICT_EVIDENCE_DIR).resolve()
        resolved.relative_to(evidence_root)
    except (OSError, ValueError):
        return None
    return resolved


def load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_non_finite_json,
        parse_float=parse_finite_float,
    )


def reject_non_finite_json(value: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number is forbidden: {value}")
    return parsed


def serialize_json_report(report: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def check_chroma_canonical(repo_root: Path) -> dict[str, Any]:
    pyproject = read_text(repo_root / "rag-mcp/pyproject.toml").lower()
    vector_store = read_text(repo_root / "rag-mcp/src/storage/vector_store.py")
    settings_model = read_text(repo_root / "rag-mcp/src/core/settings.py").lower()
    settings_yaml = read_text(repo_root / "rag-mcp/config/settings.yaml").lower()
    canary_smoke = read_text(repo_root / "rag-mcp/scripts/canary_smoke.py")
    canary_acceptance = read_text(repo_root / "rag-mcp/scripts/canary_acceptance.py")
    has_dependency = "chromadb" in pyproject
    has_adapter = "class ChromaVectorStore" in vector_store
    has_factory = "def build_vector_store" in vector_store
    default_backend = "vector_store_backend: chroma" in settings_yaml
    modeled_backend = "vector_store_backend" in settings_model
    strict_smoke_gate = "--require-chroma" in canary_smoke and "require_chroma" in canary_smoke
    strict_acceptance_gate = (
        "--require-chroma" in canary_acceptance
        and "chroma_vector_store_runtime" in canary_acceptance
    )
    has_chroma = (
        has_dependency
        and has_adapter
        and has_factory
        and default_backend
        and modeled_backend
        and strict_smoke_gate
        and strict_acceptance_gate
    )
    return check(
        name="chroma_is_canonical_vector_store",
        status="passed" if has_chroma else "blocked",
        evidence={
            "pyproject_mentions_chromadb": has_dependency,
            "chroma_vector_store_adapter": has_adapter,
            "vector_store_factory": has_factory,
            "default_backend_chroma": default_backend,
            "settings_model_backend": modeled_backend,
            "strict_canary_chroma_gate": strict_smoke_gate,
            "strict_acceptance_chroma_gate": strict_acceptance_gate,
        },
        next_action=(
            "Add the Chroma adapter and make it the canonical dense vector store, "
            "or explicitly revise the DEV_SPEC storage decision."
        ),
    )


def check_llm_judged_ragas(repo_root: Path) -> dict[str, Any]:
    scripts_dir = repo_root / "rag-mcp/scripts"
    judged_scripts = list(scripts_dir.glob("*ragas*judg*.py")) if scripts_dir.exists() else []
    readme = read_text(repo_root / "rag-mcp/README.md").lower()
    configured = bool(judged_scripts) and "faithfulness" in readme and "answer relevancy" in readme
    return check(
        name="llm_judged_ragas_gate_configured",
        status="passed" if configured else "blocked",
        evidence={
            "judged_ragas_scripts": [str(path.relative_to(repo_root)) for path in judged_scripts],
            "readme_mentions_faithfulness": "faithfulness" in readme,
            "readme_mentions_answer_relevancy": "answer relevancy" in readme,
        },
        next_action=(
            "Add a judge-model-backed RAGAS gate for faithfulness and answer "
            "relevancy before treating generation quality as production-ready."
        ),
    )


def check_vision_adapter(repo_root: Path) -> dict[str, Any]:
    libs_dir = repo_root / "rag-mcp/src/libs"
    candidate_text = "\n".join(read_text(path) for path in libs_dir.glob("*.py")) if libs_dir.exists() else ""
    has_vision = "BaseVisionLLM" in candidate_text or "Vision" in candidate_text
    return check(
        name="vision_caption_adapter_seam_present",
        status="passed" if has_vision else "warning",
        evidence={
            "libs_dir": "rag-mcp/src/libs",
            "vision_symbol_found": has_vision,
        },
        next_action=(
            "Add the disabled vision caption adapter seam if PDF/image ingestion "
            "is required for the first production cutover."
        ),
    )


def check(name: str, status: str, evidence: dict[str, Any], next_action: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence": evidence,
        "next_action": next_action,
    }


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_yaml_mapping(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return mapping_value(payload)


def mapping_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def nested_mapping(
    value: Mapping[str, Any],
    *keys: str,
) -> Mapping[str, Any]:
    return mapping_value(nested_value(value, *keys))


def nested_value(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
