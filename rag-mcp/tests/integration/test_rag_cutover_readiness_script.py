import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "rag_cutover_readiness.py"
VERIFICATION_REPORT_PATH = "rag-mcp/output/metrics/rag_canary_verification.json"
REQUIRED_STRICT_GATES = [
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
]
RETRIEVAL_EVALUATOR_CONTRACT = {
    "name": "jchatmind-stable-context-retrieval",
    "version": "1.0",
    "match_basis": "ground_truth_context_ids",
    "recall_at_1": "matched_ground_truth_ids_at_rank_1/ground_truth_context_ids",
    "mrr": "reciprocal_rank_of_first_matched_ground_truth_context_id",
}


def valid_golden_case() -> dict:
    return {
        "case_id": "case-1",
        "dataset_split": "answer_generation",
        "question": "What does the current pipeline return?",
        "ground_truth_context_ids": ["chunk-1"],
        "source_refs": [
            {
                "context_id": "chunk-1",
                "source_path": "knowledge/test.md",
            }
        ],
        "reference_contexts": ["Golden pipeline evidence."],
        "ground_truth": (
            "The current pipeline returns a generated answer from Golden evidence."
        ),
    }


def semantic_golden_case(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "ground_truth_context_ids": case["ground_truth_context_ids"],
        "source_refs": case["source_refs"],
        "reference_contexts": case["reference_contexts"],
        "ground_truth": case["ground_truth"],
        "reference_answer": (
            case.get("reference_answer") or case["ground_truth"]
        ),
    }


def canonical_sha256(value, *, sort_keys=True) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_dataset_contract() -> dict:
    semantic = semantic_golden_case(valid_golden_case())
    return {
        "case_count": 1,
        "case_ids_sha256": canonical_sha256(["case-1"], sort_keys=False),
        "cohort_sha256": canonical_sha256([semantic]),
        "cohort_fingerprint_version": "pipeline-golden-v1",
    }


def load_readiness_module():
    spec = importlib.util.spec_from_file_location("rag_cutover_readiness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["rag_cutover_readiness"] = module
    spec.loader.exec_module(module)
    return module


def write(root: Path, relative_path: str, text: str = "") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(root: Path, relative_path: str, payload: dict) -> None:
    write(root, relative_path, json.dumps(payload))


def valid_acceptance_report() -> dict:
    dataset = valid_dataset_contract()
    golden_case_sha256 = canonical_sha256(
        semantic_golden_case(valid_golden_case())
    )
    pipeline_report = {
        "version": "1.1",
        "status": "passed",
        "mode": "hybrid",
        "top_k": 5,
        "evaluator": copy.deepcopy(RETRIEVAL_EVALUATOR_CONTRACT),
        "runtime_scope": "python_query_engine",
        "vector_store_backend": "ChromaVectorStore",
        "dataset": copy.deepcopy(dataset),
        "summary": {
            "case_count": 1,
            "error_count": 0,
            "empty_answer_count": 0,
        },
        "retrieval_metrics": {
            "recall_at_1": 1.0,
            "mrr": 1.0,
        },
        "runtime_metrics": {
            "p95_latency_ms": 10.0,
            "fallback_rate": 0.0,
            "error_rate": 0.0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "golden_case_sha256": golden_case_sha256,
                "ground_truth_context_ids": ["chunk-1"],
                "retrieved_context_ids": ["chunk-1"],
                "matched_ground_truth_context_ids": ["chunk-1"],
                "retrieved_contexts": ["Golden pipeline evidence."],
                "retrieved_results": [
                    {
                        "chunk_id": "chunk-1",
                        "text": "Golden pipeline evidence.",
                        "metadata": {},
                    }
                ],
                "answer": "Generated answer [C1].",
                "answer_source": "generated_answer",
                "latency_ms": 10.0,
                "error": None,
            },
        ],
    }
    judge_input_sha256 = canonical_sha256(
        {
            "case_id": "case-1",
            "question": valid_golden_case()["question"],
            "generated_answer": "Generated answer [C1].",
            "retrieved_contexts": ["Golden pipeline evidence."],
            "reference_answer": valid_golden_case()["ground_truth"],
            "answer_source": "generated_answer",
        }
    )
    java_baseline = {
        "version": "1.1",
        "status": "passed",
        "mode": "hybrid",
        "top_k": 5,
        "evaluator": copy.deepcopy(RETRIEVAL_EVALUATOR_CONTRACT),
        "dataset": copy.deepcopy(dataset),
        "retrieval_metrics": {
            "recall_at_1": 1.0,
            "mrr": 1.0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "golden_case_sha256": golden_case_sha256,
                "ground_truth_context_ids": ["chunk-1"],
                "matched_ground_truth_context_ids": ["chunk-1"],
                "retrieved_results": [
                    {
                        "chunk_id": "chunk-1",
                        "text": "Golden pipeline evidence.",
                        "metadata": {},
                    }
                ],
            }
        ],
    }
    gate_details = {
        "current_pipeline_recall_at_1": (1.0, 0.9),
        "current_pipeline_mrr": (1.0, 0.95),
        "current_pipeline_p95_latency": (10.0, 8000.0),
        "current_pipeline_fallback_rate": (0.0, 0.01),
        "current_pipeline_error_rate": (0.0, 0.01),
        "current_pipeline_recall_at_1_degradation": (
            1.0,
            {"baseline": 1.0, "max_degradation": 0.02, "minimum": 0.98},
        ),
        "current_pipeline_mrr_degradation": (
            1.0,
            {"baseline": 1.0, "max_degradation": 0.02, "minimum": 0.98},
        ),
    }
    return {
        "version": "2.8",
        "status": "passed",
        "release_gate_source": "current_pipeline_and_runtime_smoke",
        "canary": {
            "report": {
                "vector_store": {
                    "actual_backend": "ChromaVectorStore",
                },
            },
        },
        "current_pipeline": {
            "answer_policy": "generated",
            "report": pipeline_report,
            "judge_report": {
                "version": "2.5",
                "status": "passed",
                "judge": {"provider": "google", "model": "gemini-test"},
                "case_count": 1,
                "thresholds": {
                    "min_mean_faithfulness": 0.7,
                    "min_mean_answer_relevancy": 0.7,
                    "min_case_score": 0.5,
                },
                "metrics": {
                    "faithfulness": {
                        "mean": 1.0,
                        "min": 1.0,
                        "max": 1.0,
                    },
                    "answer_relevancy": {
                        "mean": 1.0,
                        "min": 1.0,
                        "max": 1.0,
                    },
                },
                "failed_cases": [],
                "cases": [
                    {
                        "case_id": "case-1",
                        "evaluation_input_sha256": judge_input_sha256,
                        "difficulty": "easy",
                        "tactic": "direct",
                        "answer_source": "generated_answer",
                        "faithfulness": 1.0,
                        "answer_relevancy": 1.0,
                        "reason": "Supported and relevant.",
                    }
                ],
            },
            "java_baseline_required": True,
            "java_baseline_report": java_baseline,
            "java_baseline_error": None,
        },
        "gates": [
            {
                "name": name,
                "status": "passed",
                **(
                    {
                        "observed": gate_details[name][0],
                        "threshold": gate_details[name][1],
                    }
                    if name in gate_details
                    else {}
                ),
            }
            for name in REQUIRED_STRICT_GATES
        ],
    }


def valid_verification_report() -> dict:
    generated_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    rounds = [
        {
            "round": round_number,
            "step_status": "passed",
            "report_path": (
                "rag-mcp/output/metrics/"
                f"canary_acceptance_report.round-{round_number}.json"
            ),
            "report": valid_acceptance_report(),
        }
        for round_number in range(1, 4)
    ]
    return {
        "version": "3.0",
        "status": "passed",
        "strict_cutover": True,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "steps": [
            {
                "name": "python_tests",
                "status": "passed",
                "command": ["python", "-m", "pytest", "-q"],
            },
            *[
                {
                    "name": f"canary_acceptance_round_{round_number}",
                    "status": "passed",
                    "command": [
                        "python",
                        "scripts/canary_acceptance.py",
                        "--ragas-rounds",
                        "1",
                        "--require-chroma",
                        "--current-pipeline",
                        "--answer-policy",
                        "generated",
                        "--java-baseline-report",
                        "rag-mcp/data/evaluation/java_current_pipeline_baseline.json",
                        "--output-json",
                        rounds[round_number - 1]["report_path"],
                    ],
                }
                for round_number in range(1, 4)
            ],
            {
                "name": "java_bridge_tests",
                "status": "passed",
                "command": [
                    "mvnw.cmd",
                    "-q",
                    "-Dtest=!JChatMindV1Test,!JChatMindV2Test",
                    "test",
                ],
            },
        ],
        "burn_in": {
            "requested_rounds": 3,
            "completed_rounds": 3,
            "rounds": rounds,
        },
    }


def write_verification_evidence(root: Path, payload: dict) -> None:
    module = load_readiness_module()
    attestation = module.build_source_attestation(root)
    payload.setdefault("source_attestation", attestation)
    payload.setdefault("source_attestation_stable", True)

    python_executable = str(Path(sys.executable).resolve())
    java_wrapper = str(module.expected_maven_wrapper(root))
    for step in payload["steps"]:
        name = step.get("name")
        command = step.get("command")
        if isinstance(command, list) and command:
            if name == "java_bridge_tests" and command[0] in {
                "mvnw",
                "mvnw.cmd",
            }:
                command[0] = java_wrapper
            elif (
                name == "python_tests"
                or isinstance(name, str)
                and name.startswith("canary_acceptance_round_")
            ) and command[0] == "python":
                command[0] = python_executable
        if name == "java_bridge_tests":
            step.setdefault("cwd", str((root / "jchatmind").resolve()))
        else:
            step.setdefault("cwd", str((root / "rag-mcp").resolve()))
        step.setdefault("returncode", 0)

    baseline_generated_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat().replace("+00:00", "Z")
    for round_row in payload["burn_in"]["rounds"]:
        java_baseline = round_row["report"]["current_pipeline"][
            "java_baseline_report"
        ]
        java_baseline.setdefault(
            "producer",
            "jchatmind-java-current-pipeline-evaluator",
        )
        java_baseline.setdefault("runtime_scope", "java_rag_retrieval")
        java_baseline.setdefault("generated_at", baseline_generated_at)
        java_baseline.setdefault(
            "source_attestation_sha256",
            attestation["sha256"],
        )
        write_json(root, round_row["report_path"], round_row["report"])
    write_json(
        root,
        "rag-mcp/data/evaluation/java_current_pipeline_baseline.json",
        payload["burn_in"]["rounds"][0]["report"]["current_pipeline"][
            "java_baseline_report"
        ],
    )
    write_json(root, VERIFICATION_REPORT_PATH, payload)


def minimal_repo(root: Path, *, ready: bool) -> Path:
    required_files = [
        "rag-mcp/main.py",
        "rag-mcp/src/core/query_engine.py",
        "rag-mcp/src/ingestion/pipeline.py",
        "rag-mcp/src/mcp_server/server.py",
        "rag-mcp/src/observability/trace_context.py",
        "rag-mcp/scripts/ingest.py",
        "rag-mcp/scripts/query.py",
        "rag-mcp/scripts/canary_acceptance.py",
        "scripts/verify_rag_canary.py",
        "scripts/rag_cutover_readiness.py",
        ".github/workflows/rag-canary-acceptance.yml",
        "jchatmind/mvnw",
        "jchatmind/mvnw.cmd",
    ]
    for relative_path in required_files:
        write(root, relative_path)
    write(
        root,
        "jchatmind/src/main/resources/application-rag-canary.yaml",
        """
spring:
  config:
    activate:
      on-profile: rag-canary
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
    fallback-on-error: false
    fallback-on-empty: false
    fail-on-ingestion-error: true
""",
    )
    if ready:
        write(root, "scripts/generate_java_rag_baseline.py", "# Task 9B producer fixture\n")
        write(
            root,
            "jchatmind/src/main/resources/application.yaml",
            """
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
""",
        )
        write(root, "rag-mcp/pyproject.toml", 'dependencies = ["chromadb>=0.5", "ragas==0.4.3"]')
        write(
            root,
            "rag-mcp/src/storage/vector_store.py",
            "class ChromaVectorStore: pass\ndef build_vector_store(): pass",
        )
        write(root, "rag-mcp/src/core/settings.py", "vector_store_backend = 'chroma'")
        write(root, "rag-mcp/config/settings.yaml", "storage:\n  vector_store_backend: chroma\n")
        write(root, "rag-mcp/scripts/canary_smoke.py", "--require-chroma\nrequire_chroma")
        write(
            root,
            "rag-mcp/scripts/canary_acceptance.py",
            "--require-chroma\nchroma_vector_store_runtime",
        )
        write(root, "rag-mcp/scripts/evaluate_ragas_judged.py")
        write(root, "rag-mcp/src/libs/vision.py", "class BaseVisionLLM: pass")
        write(root, "rag-mcp/README.md", "faithfulness and answer relevancy")
        write(
            root,
            "rag-mcp/data/evaluation/ragas_cases.combined.jsonl",
            json.dumps(valid_golden_case()) + "\n",
        )
        verification = valid_verification_report()
        write_json(
            root,
            "rag-mcp/data/evaluation/java_current_pipeline_baseline.json",
            verification["burn_in"]["rounds"][0]["report"]
            ["current_pipeline"]["java_baseline_report"],
        )
        write_verification_evidence(root, verification)
    else:
        write(
            root,
            "jchatmind/src/main/resources/application.yaml",
            """
rag:
  python-bridge:
    enabled: false
    ingestion-enabled: false
    readiness-gate-enabled: false
    canary-preflight-enabled: false
    canary-preflight-fail-on-error: false
  self-rag:
    enabled: true
""",
        )
        write(root, "rag-mcp/pyproject.toml", 'dependencies = ["pytest>=8"]')
        write(root, "rag-mcp/src/storage/vector_store.py", "class SqliteVectorStore: pass")
        write(root, "rag-mcp/src/core/settings.py", "vector_store_db = 'data/db/vector_store.db'")
        write(root, "rag-mcp/README.md", "faithfulness requires a judge")
        write(root, "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java")
    return root


def test_not_ready_repo_reports_concrete_blockers(tmp_path):
    module = load_readiness_module()

    report = module.evaluate_readiness(minimal_repo(tmp_path, ready=False))

    assert report["status"] == "not_ready"
    assert "default_profile_delegates_to_python" in report["blockers"]
    default_bridge = next(
        check
        for check in report["checks"]
        if check["name"] == "default_profile_delegates_to_python"
    )
    assert "enabled: true" in default_bridge["evidence"]["missing_enabled_settings"]
    assert "java_rag_internals_retired_or_deprecated" in report["blockers"]
    assert "chroma_is_canonical_vector_store" in report["blockers"]
    assert "current_pipeline_gate_passed" in report["blockers"]
    assert "vision_caption_adapter_seam_present" in report["warnings"]


def test_ready_repo_passes_cutover_gate(tmp_path):
    module = load_readiness_module()

    report = module.evaluate_readiness(minimal_repo(tmp_path, ready=True))

    assert report["status"] == "ready"
    assert report["blockers"] == []
    assert report["summary"]["warnings"] == 0
    pipeline_gate = next(
        check
        for check in report["checks"]
        if check["name"] == "current_pipeline_gate_passed"
    )
    assert pipeline_gate["status"] == "passed"


def test_missing_java_baseline_producer_blocks_otherwise_ready_repo(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    (root / "scripts/generate_java_rag_baseline.py").unlink()

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    assert "java_baseline_producer_present" in report["blockers"]


@pytest.mark.parametrize(
    "violation",
    [
        "malformed_json",
        "stale",
        "invalid_generated_at",
        "insufficient_requested_rounds",
        "missing_requested_round",
    ],
)
def test_current_pipeline_gate_blocks_missing_or_invalid_burn_in_report(
    tmp_path,
    violation,
):
    module = load_readiness_module()
    root = minimal_repo(tmp_path / violation, ready=True)
    report_path = root / VERIFICATION_REPORT_PATH
    payload = valid_verification_report()
    if violation == "malformed_json":
        write(root, VERIFICATION_REPORT_PATH, "{")
    elif violation == "stale":
        payload["generated_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        ).isoformat()
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "invalid_generated_at":
        payload["generated_at"] = "not-a-timestamp"
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "insufficient_requested_rounds":
        payload["burn_in"]["requested_rounds"] = 2
        payload["burn_in"]["rounds"] = payload["burn_in"]["rounds"][:2]
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "missing_requested_round":
        payload["burn_in"]["requested_rounds"] = 3
        payload["burn_in"]["rounds"] = payload["burn_in"]["rounds"][:2]
        write_json(root, VERIFICATION_REPORT_PATH, payload)

    assert report_path.exists()
    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    assert "current_pipeline_gate_passed" in report["blockers"]


@pytest.mark.parametrize(
    "violation",
    [
        "verification_version",
        "acceptance_version",
        "strict_cutover",
        "missing_report_path",
        "round_step",
        "acceptance_status",
        "release_source",
        "canary_chroma",
        "pipeline_chroma",
        "answer_policy",
        "judge",
        "missing_required_gate",
        "failed_required_gate",
        "failed_extra_gate",
        "completed_rounds",
        "round_number",
        "python_tests_skipped",
        "java_tests_missing",
    ],
)
def test_current_pipeline_gate_rejects_non_strict_rounds(tmp_path, violation):
    module = load_readiness_module()
    root = minimal_repo(tmp_path / violation, ready=True)
    payload = copy.deepcopy(valid_verification_report())
    acceptance = payload["burn_in"]["rounds"][0]["report"]
    if violation == "verification_version":
        payload["version"] = "2.9"
    elif violation == "acceptance_version":
        acceptance["version"] = "2.7"
    elif violation == "strict_cutover":
        payload["strict_cutover"] = False
    elif violation == "missing_report_path":
        payload["burn_in"]["rounds"][0]["report_path"] = ""
    elif violation == "round_step":
        payload["burn_in"]["rounds"][0]["step_status"] = "failed"
    elif violation == "acceptance_status":
        acceptance["status"] = "failed"
    elif violation == "release_source":
        acceptance["release_gate_source"] = "all_gates"
    elif violation == "canary_chroma":
        acceptance["canary"]["report"]["vector_store"]["actual_backend"] = (
            "SqliteVectorStore"
        )
    elif violation == "pipeline_chroma":
        acceptance["current_pipeline"]["report"]["vector_store_backend"] = (
            "SqliteVectorStore"
        )
    elif violation == "answer_policy":
        acceptance["current_pipeline"]["answer_policy"] = "reference"
    elif violation == "judge":
        acceptance["current_pipeline"]["judge_report"]["status"] = "failed"
    elif violation == "missing_required_gate":
        acceptance["gates"] = [
            gate
            for gate in acceptance["gates"]
            if gate["name"] != "current_pipeline_p95_latency"
        ]
    elif violation == "failed_required_gate":
        next(
            gate
            for gate in acceptance["gates"]
            if gate["name"] == "current_pipeline_fallback_rate"
        )["status"] = "failed"
    elif violation == "failed_extra_gate":
        acceptance["gates"].append({"name": "future_strict_gate", "status": "failed"})
    elif violation == "completed_rounds":
        payload["burn_in"]["completed_rounds"] = 2
    elif violation == "round_number":
        payload["burn_in"]["rounds"][1]["round"] = 1
    elif violation == "python_tests_skipped":
        payload["steps"][0]["status"] = "skipped"
    elif violation == "java_tests_missing":
        payload["steps"] = [payload["steps"][0]]
    write_json(root, VERIFICATION_REPORT_PATH, payload)

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    assert "current_pipeline_gate_passed" in report["blockers"]


@pytest.mark.parametrize(
    "violation",
    [
        "missing_artifact",
        "duplicate_artifact_path",
        "artifact_mismatch",
        "duplicate_python_step",
        "narrowed_java_suite",
        "too_many_rounds",
        "non_finite_json",
        "overflow_float",
    ],
)
def test_current_pipeline_gate_rejects_unverifiable_provenance(tmp_path, violation):
    module = load_readiness_module()
    root = minimal_repo(tmp_path / violation, ready=True)
    payload = copy.deepcopy(valid_verification_report())

    if violation == "missing_artifact":
        (root / payload["burn_in"]["rounds"][0]["report_path"]).unlink()
    elif violation == "duplicate_artifact_path":
        duplicate_path = payload["burn_in"]["rounds"][0]["report_path"]
        payload["burn_in"]["rounds"][1]["report_path"] = duplicate_path
        payload["steps"][2]["command"][-1] = duplicate_path
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "artifact_mismatch":
        write_json(
            root,
            payload["burn_in"]["rounds"][0]["report_path"],
            {"status": "failed"},
        )
    elif violation == "duplicate_python_step":
        payload["steps"].insert(1, copy.deepcopy(payload["steps"][0]))
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "narrowed_java_suite":
        payload["steps"][-1]["command"][2] = "-Dtest=OnePassingTest"
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "too_many_rounds":
        payload["burn_in"]["requested_rounds"] = 4
        payload["burn_in"]["completed_rounds"] = 4
        payload["burn_in"]["rounds"].append(
            {
                "round": 4,
                "step_status": "passed",
                "report_path": (
                    "rag-mcp/output/metrics/canary_acceptance_report.round-4.json"
                ),
                "report": valid_acceptance_report(),
            }
        )
        write_verification_evidence(root, payload)
    elif violation == "non_finite_json":
        payload["unexpected_metric"] = float("nan")
        write_json(root, VERIFICATION_REPORT_PATH, payload)
    elif violation == "overflow_float":
        serialized = json.dumps(payload)
        write(
            root,
            VERIFICATION_REPORT_PATH,
            serialized[:-1] + ',"unexpected_metric":1e400}',
        )

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    assert "current_pipeline_gate_passed" in report["blockers"]


def test_current_pipeline_gate_rejects_replayed_evidence_after_source_change(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)

    write(
        root,
        "rag-mcp/src/core/query_engine.py",
        'raise RuntimeError("runtime changed after verification")\n',
    )

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    gate = next(
        check
        for check in report["checks"]
        if check["name"] == "current_pipeline_gate_passed"
    )
    assert "source-tree attestation" in " ".join(gate["evidence"]["errors"])


@pytest.mark.parametrize(
    ("violation", "expected_error"),
    [
        ("python_executable", "current Python executable"),
        ("java_executable", "repository Maven wrapper"),
        ("acceptance_executable", "command is not strict"),
        ("python_cwd", "python_tests cwd must be"),
        ("java_cwd", "java_bridge_tests cwd must be"),
        ("acceptance_cwd", "canary_acceptance_round_1 cwd must be"),
        ("python_returncode", "python_tests returncode must be 0"),
        (
            "acceptance_returncode",
            "canary_acceptance_round_1 returncode must be 0",
        ),
        ("java_returncode", "java_bridge_tests returncode must be 0"),
    ],
)
def test_current_pipeline_gate_validates_full_step_provenance(
    tmp_path,
    violation,
    expected_error,
):
    module = load_readiness_module()
    root = minimal_repo(tmp_path / violation, ready=True)
    payload = copy.deepcopy(valid_verification_report())

    if violation == "python_executable":
        payload["steps"][0]["command"][0] = "echo"
    elif violation == "java_executable":
        payload["steps"][-1]["command"][0] = "echo"
    elif violation == "acceptance_executable":
        payload["steps"][1]["command"][0] = "echo"
    elif violation == "python_cwd":
        payload["steps"][0]["cwd"] = str((root / "jchatmind").resolve())
    elif violation == "java_cwd":
        payload["steps"][-1]["cwd"] = str((root / "rag-mcp").resolve())
    elif violation == "acceptance_cwd":
        payload["steps"][1]["cwd"] = str((root / "jchatmind").resolve())
    elif violation == "python_returncode":
        payload["steps"][0]["returncode"] = 1
    elif violation == "acceptance_returncode":
        payload["steps"][1]["returncode"] = 1
    elif violation == "java_returncode":
        payload["steps"][-1]["returncode"] = 1
    write_verification_evidence(root, payload)

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    gate = next(
        check
        for check in report["checks"]
        if check["name"] == "current_pipeline_gate_passed"
    )
    messages = list(gate["evidence"]["errors"])
    for invalid_round in gate["evidence"].get("invalid_rounds", []):
        messages.extend(invalid_round["errors"])
    assert expected_error in " ".join(messages)


@pytest.mark.parametrize(
    "violation",
    [
        "hollow_pipeline",
        "gate_observed_mismatch",
        "mock_judge",
        "baseline_cohort_mismatch",
        "pipeline_metric_self_report",
        "pipeline_latency_self_report",
        "pipeline_fallback_self_report",
        "judge_scores_self_report",
        "judge_thresholds",
        "judge_version",
        "judge_input_replay",
        "baseline_case_metrics",
        "pipeline_forged_match",
        "baseline_forged_match",
        "baseline_producer",
        "baseline_runtime_scope",
        "baseline_generated_at",
        "baseline_source_attestation",
        "baseline_top_k",
        "baseline_evaluator",
        "local_semantics",
    ],
)
def test_current_pipeline_gate_recomputes_critical_evidence(tmp_path, violation):
    module = load_readiness_module()
    root = minimal_repo(tmp_path / violation, ready=True)
    payload = copy.deepcopy(valid_verification_report())
    for round_row in payload["burn_in"]["rounds"]:
        acceptance = round_row["report"]
        current = acceptance["current_pipeline"]
        if violation == "hollow_pipeline":
            current["report"] = {
                "status": "passed",
                "vector_store_backend": "ChromaVectorStore",
            }
        elif violation == "gate_observed_mismatch":
            next(
                gate
                for gate in acceptance["gates"]
                if gate["name"] == "current_pipeline_p95_latency"
            )["observed"] = 1.0
        elif violation == "mock_judge":
            current["judge_report"]["judge"] = {
                "provider": "deterministic",
                "model": "offline-overlap",
            }
        elif violation == "baseline_cohort_mismatch":
            current["java_baseline_report"]["dataset"] = {
                "case_count": 1,
                "case_ids_sha256": "b" * 64,
            }
        elif violation == "pipeline_metric_self_report":
            current["report"]["cases"][0][
                "matched_ground_truth_context_ids"
            ] = []
            current["report"]["cases"][0]["retrieved_context_ids"] = []
            current["report"]["cases"][0]["retrieved_contexts"] = []
        elif violation == "pipeline_latency_self_report":
            current["report"]["cases"][0]["latency_ms"] = 9000.0
        elif violation == "pipeline_fallback_self_report":
            current["report"]["cases"][0]["answer_source"] = (
                "evidence_fallback"
            )
        elif violation == "judge_scores_self_report":
            current["judge_report"]["cases"][0]["faithfulness"] = 0.0
            current["judge_report"]["cases"][0]["answer_relevancy"] = 0.0
        elif violation == "judge_thresholds":
            current["judge_report"]["thresholds"][
                "min_case_score"
            ] = 0.0
        elif violation == "judge_version":
            current["judge_report"]["version"] = "999.0"
        elif violation == "judge_input_replay":
            current["report"]["cases"][0]["answer"] = (
                "A different generated answer [C1]."
            )
        elif violation == "baseline_case_metrics":
            current["java_baseline_report"]["cases"][0][
                "matched_ground_truth_context_ids"
            ] = []
        elif violation == "pipeline_forged_match":
            current["report"]["cases"][0]["retrieved_results"] = [
                {
                    "chunk_id": "unrelated-runtime-chunk",
                    "text": "Completely unrelated retrieved passage.",
                    "metadata": {},
                }
            ]
        elif violation == "baseline_forged_match":
            current["java_baseline_report"]["cases"][0][
                "retrieved_results"
            ] = [
                {
                    "chunk_id": "unrelated-java-chunk",
                    "text": "Completely unrelated retrieved passage.",
                    "metadata": {},
                }
            ]
        elif violation == "baseline_producer":
            current["java_baseline_report"]["producer"] = "hand-written"
        elif violation == "baseline_runtime_scope":
            current["java_baseline_report"]["runtime_scope"] = "unknown"
        elif violation == "baseline_generated_at":
            current["java_baseline_report"]["generated_at"] = (
                "not-a-timestamp"
            )
        elif violation == "baseline_source_attestation":
            current["java_baseline_report"][
                "source_attestation_sha256"
            ] = "0" * 64
        elif violation == "baseline_top_k":
            current["java_baseline_report"]["top_k"] = 4
        elif violation == "baseline_evaluator":
            current["java_baseline_report"]["evaluator"]["version"] = "2.0"

    if violation == "local_semantics":
        changed_golden = valid_golden_case()
        changed_golden["question"] = "What changed in the current pipeline?"
        write(
            root,
            "rag-mcp/data/evaluation/ragas_cases.combined.jsonl",
            json.dumps(changed_golden) + "\n",
        )

    baseline = payload["burn_in"]["rounds"][0]["report"]
    baseline = baseline["current_pipeline"]["java_baseline_report"]
    write_json(
        root,
        "rag-mcp/data/evaluation/java_current_pipeline_baseline.json",
        baseline,
    )
    write_verification_evidence(root, payload)

    report = module.evaluate_readiness(root)

    assert report["status"] == "not_ready"
    assert "current_pipeline_gate_passed" in report["blockers"]


def test_judge_input_hash_uses_generated_answer_loader_normalization(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    payload = copy.deepcopy(valid_verification_report())
    for round_row in payload["burn_in"]["rounds"]:
        round_row["report"]["current_pipeline"]["report"]["cases"][0][
            "answer"
        ] = "  Generated answer [C1].  "
    write_verification_evidence(root, payload)

    report = module.evaluate_readiness(root)

    assert report["status"] == "ready"
    assert "current_pipeline_gate_passed" not in report["blockers"]


def test_judge_input_hash_preserves_raw_golden_prompt_strings(tmp_path):
    module = load_readiness_module()
    golden = valid_golden_case()
    golden["question"] = "  What does the current pipeline return?  "
    golden["reference_answer"] = "  A prompt-sensitive reference answer.  "
    write(
        tmp_path,
        "rag-mcp/data/evaluation/ragas_cases.combined.jsonl",
        json.dumps(golden) + "\n",
    )
    cohort, cohort_errors = module.load_golden_cohort(tmp_path)
    assert cohort_errors == []
    pipeline = valid_acceptance_report()["current_pipeline"]["report"]
    pipeline["dataset"] = cohort["dataset"]
    pipeline["cases"][0]["golden_case_sha256"] = cohort["cases_by_id"][
        "case-1"
    ]["golden_case_sha256"]

    evidence, evidence_errors = module.recompute_report_evidence(
        pipeline,
        cohort,
        label="current pipeline",
        require_runtime=True,
    )

    assert evidence_errors == []
    assert evidence["judge_input_sha256_by_case"]["case-1"] == (
        canonical_sha256(
            {
                "case_id": "case-1",
                "question": golden["question"],
                "generated_answer": "Generated answer [C1].",
                "retrieved_contexts": ["Golden pipeline evidence."],
                "reference_answer": golden["reference_answer"],
                "answer_source": "generated_answer",
            }
        )
    )


def test_readiness_replays_every_runner_ground_truth_match_route():
    module = load_readiness_module()
    golden_case = {
        "ground_truth_context_ids": ["chunk-1"],
        "source_refs": [
            {
                "context_id": "chunk-1",
                "source_path": "knowledge/test.md",
                "heading": "Relevant heading",
            }
        ],
        "reference_contexts": [
            "Golden pipeline evidence with enough detail to match."
        ],
    }
    retrieved_results = [
        {
            "chunk_id": "chunk-1",
            "text": "Unrelated direct-ID evidence.",
            "metadata": {},
        },
        {
            "chunk_id": "runtime-metadata-id",
            "text": "Unrelated metadata-ID evidence.",
            "metadata": {"golden_context_id": "chunk-1"},
        },
        {
            "chunk_id": "runtime-source-id",
            "text": "Unrelated source evidence.",
            "metadata": {
                "source_path": "D:/docs/knowledge/test.md",
                "title": "Relevant heading",
            },
        },
        {
            "chunk_id": "runtime-text-id",
            "text": "Golden pipeline evidence with enough detail to match.",
            "metadata": {},
        },
    ]

    assert [
        module.match_ground_truth_context(result, golden_case)
        for result in retrieved_results
    ] == ["chunk-1", "chunk-1", "chunk-1", "chunk-1"]
    assert (
        module.match_ground_truth_context(
            {
                "chunk_id": "unrelated",
                "text": "Completely unrelated retrieved passage.",
                "metadata": {},
            },
            golden_case,
        )
        is None
    )


def test_yaml_checks_require_exact_boolean_keys(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    write(
        root,
        "jchatmind/src/main/resources/application.yaml",
        """
rag:
  python-bridge:
    enabled: false
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
""",
    )

    report = module.evaluate_readiness(root)

    assert "default_profile_delegates_to_python" in report["blockers"]
    default_bridge = next(
        check
        for check in report["checks"]
        if check["name"] == "default_profile_delegates_to_python"
    )
    assert default_bridge["evidence"]["missing_enabled_settings"] == ["enabled: true"]


def test_canary_profile_requires_exact_activation_value(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    write(
        root,
        "jchatmind/src/main/resources/application-rag-canary.yaml",
        """
spring:
  config:
    activate:
      on-profile: not-rag-canary
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
""",
    )

    report = module.evaluate_readiness(root)

    assert "rag_canary_profile_is_fail_fast" in report["blockers"]


def test_canary_profile_requires_fail_closed_fallback_settings(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    write(
        root,
        "jchatmind/src/main/resources/application-rag-canary.yaml",
        """
spring:
  config:
    activate:
      on-profile: rag-canary
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
    fallback-on-error: true
    fallback-on-empty: false
    fail-on-ingestion-error: true
""",
    )

    report = module.evaluate_readiness(root)

    assert "rag_canary_profile_is_fail_fast" in report["blockers"]
    canary = next(
        check
        for check in report["checks"]
        if check["name"] == "rag_canary_profile_is_fail_fast"
    )
    assert "fallback-on-error: false" in canary["evidence"]["missing_settings"]


@pytest.mark.parametrize(
    "annotation",
    [
        "@Deprecated",
        "// @Deprecated(forRemoval = true)",
        "/*\n@Deprecated(forRemoval = true)\n*/",
        '@SuppressWarnings("@Deprecated(forRemoval = true)")',
        'private static final String NOTE = """\n@Deprecated(forRemoval = true)\n""";',
    ],
)
def test_java_retirement_requires_real_for_removal_annotation(tmp_path, annotation):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    write(
        root,
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java",
        f"{annotation}\npublic class RagServiceImpl {{}}\n",
    )

    report = module.evaluate_readiness(root)

    assert "java_rag_internals_retired_or_deprecated" in report["blockers"]


def test_java_retirement_rejects_method_only_for_removal_annotation(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    write(
        root,
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java",
        """
public class RagServiceImpl {
    @Deprecated(forRemoval = true)
    public void oldMethod() {}
}
""",
    )

    report = module.evaluate_readiness(root)

    assert "java_rag_internals_retired_or_deprecated" in report["blockers"]


def test_java_retirement_accepts_for_removal_annotation(tmp_path):
    module = load_readiness_module()
    root = minimal_repo(tmp_path, ready=True)
    for class_name in ("RagServiceImpl", "GraphRagServiceImpl"):
        write(
            root,
            (
                "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/"
                f"{class_name}.java"
            ),
            f"@Deprecated(forRemoval = true)\npublic class {class_name} {{}}\n",
        )

    report = module.evaluate_readiness(root)

    assert "java_rag_internals_retired_or_deprecated" not in report["blockers"]


def test_cli_returns_nonzero_unless_allow_not_ready(tmp_path):
    minimal_repo(tmp_path, ready=False)

    blocked = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    allowed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
            "--allow-not-ready",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert blocked.returncode == 1
    assert allowed.returncode == 0
    assert '"status": "not_ready"' in allowed.stdout
