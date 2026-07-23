import copy
import hashlib
import json

import pytest

from scripts.canary_acceptance import _run_current_pipeline_judge, main, run_acceptance
from src.evaluation.pipeline_runner import RETRIEVAL_EVALUATOR_CONTRACT


CURRENT_PIPELINE_NUMERIC_GATES = [
    (
        "retrieval_metrics",
        "recall_at_1",
        "current_pipeline_recall_at_1_degradation",
    ),
    ("retrieval_metrics", "mrr", "current_pipeline_mrr_degradation"),
    ("runtime_metrics", "p95_latency_ms", "current_pipeline_p95_latency"),
    ("runtime_metrics", "fallback_rate", "current_pipeline_fallback_rate"),
    ("runtime_metrics", "error_rate", "current_pipeline_error_rate"),
]
CASE_IDS_SHA256 = hashlib.sha256(b'["case-1"]').hexdigest()
COHORT_SHA256 = "c" * 64
GOLDEN_CASE_SHA256 = "d" * 64
DATASET_CONTRACT = {
    "case_count": 1,
    "case_ids_sha256": CASE_IDS_SHA256,
    "cohort_sha256": COHORT_SHA256,
    "cohort_fingerprint_version": "pipeline-golden-v1",
}


def valid_current_pipeline_report():
    return {
        "version": "1.1",
        "status": "passed",
        "mode": "hybrid",
        "top_k": 5,
        "evaluator": copy.deepcopy(RETRIEVAL_EVALUATOR_CONTRACT),
        "runtime_scope": "python_query_engine",
        "vector_store_backend": "ChromaVectorStore",
        "dataset": copy.deepcopy(DATASET_CONTRACT),
        "summary": {
            "case_count": 1,
            "error_count": 0,
            "empty_answer_count": 0,
        },
        "retrieval_metrics": {"recall_at_1": 1.0, "mrr": 1.0},
        "runtime_metrics": {
            "p95_latency_ms": 10.0,
            "fallback_rate": 0.0,
            "error_rate": 0.0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "golden_case_sha256": GOLDEN_CASE_SHA256,
                "ground_truth_context_ids": ["chunk-1"],
                "matched_ground_truth_context_ids": ["chunk-1"],
                "answer": "Live answer [C1].",
                "answer_source": "generated_answer",
                "retrieved_context_ids": ["chunk-1"],
                "retrieved_contexts": ["Live evidence."],
                "retrieved_results": [
                    {
                        "chunk_id": "chunk-1",
                        "text": "Live evidence.",
                        "metadata": {},
                    }
                ],
                "latency_ms": 10.0,
                "error": None,
            }
        ],
    }


def valid_current_pipeline_judge_report():
    return {
        "status": "passed",
        "case_count": 1,
        "metrics": {
            "faithfulness": {"mean": 1.0, "min": 1.0, "max": 1.0},
            "answer_relevancy": {"mean": 1.0, "min": 1.0, "max": 1.0},
        },
    }


def valid_java_baseline_report():
    return {
        "version": "1.1",
        "producer": "jchatmind-java-current-pipeline-evaluator",
        "runtime_scope": "java_rag_retrieval",
        "generated_at": "2020-01-01T00:00:00Z",
        "source_attestation_sha256": "a" * 64,
        "status": "passed",
        "mode": "hybrid",
        "top_k": 5,
        "evaluator": copy.deepcopy(RETRIEVAL_EVALUATOR_CONTRACT),
        "dataset": copy.deepcopy(DATASET_CONTRACT),
        "retrieval_metrics": {
            "recall_at_1": 1.0,
            "mrr": 1.0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "golden_case_sha256": GOLDEN_CASE_SHA256,
                "ground_truth_context_ids": ["chunk-1"],
                "matched_ground_truth_context_ids": ["chunk-1"],
                "retrieved_results": [
                    {
                        "chunk_id": "chunk-1",
                        "text": "Live evidence.",
                        "metadata": {},
                    }
                ],
            }
        ],
    }


def test_canary_current_pipeline_requires_preindexed_collection(monkeypatch, tmp_path):
    captured = {}

    def current_pipeline(**kwargs):
        captured.update(kwargs)
        return valid_current_pipeline_report()

    monkeypatch.setattr(
        "scripts.canary_acceptance.run_current_pipeline",
        current_pipeline,
    )

    from scripts.canary_acceptance import _run_current_pipeline

    _run_current_pipeline(tmp_path, "acceptance-canary")

    assert captured["require_indexed_collection"] is True


def test_run_acceptance_without_smoke_checks_stable_ragas(tmp_path):
    output_json = tmp_path / "acceptance.json"

    report = run_acceptance(
        output_json=output_json,
        run_smoke=False,
        ragas_rounds=2,
    )

    assert report["status"] == "passed"
    assert report["version"] == "2.8"
    assert report["canary"]["skipped"] is True
    assert report["ragas"]["stable"] is True
    assert len(report["ragas"]["rounds"]) == 2
    assert len({row["sha256"] for row in report["ragas"]["rounds"]}) == 1
    assert report["ragas"]["report"]["inventory"]["total_cases"] >= 1000
    assert json.loads(output_json.read_text(encoding="utf-8")) == report


def test_run_acceptance_reports_failed_threshold_without_throwing():
    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        min_total_cases=999999,
    )

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "ragas_total_cases" in failed_gates


def test_run_acceptance_reports_smoke_failure_without_throwing(monkeypatch):
    def fail_smoke(_collection, *, require_chroma):
        raise AssertionError("smoke failed")

    monkeypatch.setattr("scripts.canary_acceptance._run_smoke_canary", fail_smoke)

    report = run_acceptance(ragas_rounds=1)

    assert report["status"] == "failed"
    assert report["canary"]["error"] == "smoke failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "canary_smoke" in failed_gates


def test_run_acceptance_can_require_chroma_runtime(monkeypatch):
    def fallback_smoke(_collection, *, require_chroma):
        return {"vector_store": {"actual_backend": "SqliteVectorStore"}}

    monkeypatch.setattr("scripts.canary_acceptance._run_smoke_canary", fallback_smoke)

    report = run_acceptance(ragas_rounds=1, require_chroma=True)

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "chroma_vector_store_runtime" in failed_gates


def test_canary_acceptance_cli_writes_json(tmp_path):
    output_json = tmp_path / "cli-acceptance.json"

    exit_code = main(
        [
            "--skip-smoke",
            "--ragas-rounds",
            "2",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["canary"]["skipped"] is True
    assert len(report["ragas"]["rounds"]) == 2


def test_canary_acceptance_cli_forwards_current_pipeline_thresholds(monkeypatch):
    captured = {}

    def acceptance(**kwargs):
        captured.update(kwargs)
        return {"status": "passed"}

    monkeypatch.setattr("scripts.canary_acceptance.run_acceptance", acceptance)

    exit_code = main(
        [
            "--skip-smoke",
            "--current-pipeline",
            "--answer-policy",
            "generated",
            "--java-baseline-recall-at-1",
            "0.8",
            "--java-baseline-mrr",
            "0.9",
            "--max-retrieval-degradation",
            "0.03",
            "--max-p95-latency-ms",
            "7000",
            "--max-fallback-rate",
            "0.005",
            "--max-error-rate",
            "0.006",
        ]
    )

    assert exit_code == 0
    assert captured["java_baseline_recall_at_1"] == 0.8
    assert captured["java_baseline_mrr"] == 0.9
    assert captured["max_degradation"] == 0.03
    assert captured["max_p95_latency_ms"] == 7000.0
    assert captured["max_fallback_rate"] == 0.005
    assert captured["max_error_rate"] == 0.006


def test_current_pipeline_generated_answer_gate_passes_live_chroma_report(monkeypatch):
    def current_pipeline(_dataset_dir, _collection):
        return valid_current_pipeline_report()

    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        current_pipeline,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
        raising=False,
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "passed"
    assert report["current_pipeline"]["enabled"] is True
    assert report["current_pipeline"]["answer_policy"] == "generated"
    assert report["current_pipeline"]["report"]["cases"][0]["answer"] == (
        "Live answer [C1]."
    )
    current_gates = {
        gate["name"]: gate["status"]
        for gate in report["gates"]
        if gate["name"].startswith("current_pipeline")
    }
    assert current_gates == {
        "current_pipeline_report_passed": "passed",
        "current_pipeline_executed": "passed",
        "current_pipeline_generated_answers": "passed",
        "current_pipeline_cases_present": "passed",
        "current_pipeline_no_case_errors": "passed",
        "current_pipeline_nonempty_answers": "passed",
        "current_pipeline_no_reference_fallback": "passed",
        "current_pipeline_chroma_backend": "passed",
        "current_pipeline_recall_at_1": "passed",
        "current_pipeline_recall_at_1_degradation": "passed",
        "current_pipeline_mrr": "passed",
        "current_pipeline_mrr_degradation": "passed",
        "current_pipeline_p95_latency": "passed",
        "current_pipeline_fallback_rate": "passed",
        "current_pipeline_error_rate": "passed",
        "current_pipeline_judged_answers": "passed",
    }


@pytest.mark.parametrize("mismatch", [False, True])
def test_current_pipeline_java_baseline_must_use_same_case_cohort(
    monkeypatch,
    tmp_path,
    mismatch,
):
    pipeline_report = valid_current_pipeline_report()
    baseline_report = valid_java_baseline_report()
    if mismatch:
        baseline_report["dataset"]["case_ids_sha256"] = "different-cohort"
    baseline_path = tmp_path / "java-baseline.json"
    baseline_path.write_text(json.dumps(baseline_report), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
        java_baseline_report_path=baseline_path,
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_java_baseline_comparable"
    )
    assert gate["status"] == ("failed" if mismatch else "passed")
    assert report["status"] == ("failed" if mismatch else "passed")


@pytest.mark.parametrize(
    "violation",
    [
        "version",
        "producer",
        "runtime_scope",
        "generated_at",
        "source_attestation",
        "top_k",
        "evaluator",
        "case_coverage",
        "case_metrics",
    ],
)
def test_current_pipeline_java_baseline_binds_full_retrieval_contract(
    monkeypatch,
    tmp_path,
    violation,
):
    pipeline_report = valid_current_pipeline_report()
    baseline_report = valid_java_baseline_report()
    if violation == "version":
        baseline_report["version"] = "1.0"
    elif violation == "producer":
        baseline_report["producer"] = "hand-written"
    elif violation == "runtime_scope":
        baseline_report["runtime_scope"] = "unknown"
    elif violation == "generated_at":
        baseline_report["generated_at"] = "not-a-timestamp"
    elif violation == "source_attestation":
        baseline_report["source_attestation_sha256"] = "not-a-sha256"
    elif violation == "top_k":
        baseline_report["top_k"] = 4
    elif violation == "evaluator":
        baseline_report["evaluator"]["version"] = "different"
    elif violation == "case_coverage":
        baseline_report["cases"][0]["case_id"] = "other-case"
    elif violation == "case_metrics":
        baseline_report["cases"][0][
            "matched_ground_truth_context_ids"
        ] = []
    baseline_path = tmp_path / "java-baseline.json"
    baseline_path.write_text(json.dumps(baseline_report), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: (
            valid_current_pipeline_judge_report()
        ),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
        java_baseline_report_path=baseline_path,
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_java_baseline_comparable"
    )
    assert gate["status"] == "failed"
    assert report["status"] == "failed"


def test_java_baseline_loader_rejects_overflowed_json_float(
    monkeypatch,
    tmp_path,
):
    baseline_path = tmp_path / "java-baseline.json"
    baseline_path.write_text(
        '{"retrieval_metrics":{"recall_at_1":1e400}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: valid_current_pipeline_report(),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: (
            valid_current_pipeline_judge_report()
        ),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
        java_baseline_report_path=baseline_path,
    )

    assert report["status"] == "failed"
    assert "non-finite JSON number" in (
        report["current_pipeline"]["java_baseline_error"]
    )


@pytest.mark.parametrize(
    ("recall_at_1", "expected_status"),
    [
        (0.9098, "passed"),
        (0.909799, "failed"),
    ],
)
def test_current_pipeline_recall_degradation_gate_uses_java_hybrid_baseline(
    monkeypatch,
    recall_at_1,
    expected_status,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["retrieval_metrics"]["recall_at_1"] = recall_at_1
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_recall_at_1_degradation"
    )
    assert gate["status"] == expected_status
    assert gate["observed"] == recall_at_1
    assert gate["threshold"] == {
        "baseline": 0.9298,
        "max_degradation": 0.02,
        "minimum": pytest.approx(0.9098),
    }


@pytest.mark.parametrize(
    ("mrr", "expected_status"),
    [
        (0.9449, "passed"),
        (0.944899, "failed"),
    ],
)
def test_current_pipeline_mrr_degradation_gate_uses_java_hybrid_baseline(
    monkeypatch,
    mrr,
    expected_status,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["retrieval_metrics"]["mrr"] = mrr
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        min_mrr=0.0,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_mrr_degradation"
    )
    assert gate["status"] == expected_status
    assert gate["observed"] == mrr
    assert gate["threshold"] == {
        "baseline": 0.9649,
        "max_degradation": 0.02,
        "minimum": pytest.approx(0.9449),
    }


@pytest.mark.parametrize(
    ("p95_latency_ms", "expected_status"),
    [
        (8000.0, "passed"),
        (8000.001, "failed"),
    ],
)
def test_current_pipeline_p95_latency_gate_enforces_ceiling(
    monkeypatch,
    p95_latency_ms,
    expected_status,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["runtime_metrics"]["p95_latency_ms"] = p95_latency_ms
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_p95_latency"
    )
    assert gate["status"] == expected_status
    assert gate["observed"] == p95_latency_ms
    assert gate["threshold"] == 8000.0


@pytest.mark.parametrize(
    ("fallback_rate", "expected_status"),
    [
        (0.01, "passed"),
        (0.010001, "failed"),
    ],
)
def test_current_pipeline_fallback_rate_gate_enforces_ceiling(
    monkeypatch,
    fallback_rate,
    expected_status,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["runtime_metrics"]["fallback_rate"] = fallback_rate
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_fallback_rate"
    )
    assert gate["status"] == expected_status
    assert gate["observed"] == fallback_rate
    assert gate["threshold"] == 0.01


@pytest.mark.parametrize(
    ("error_rate", "expected_status"),
    [
        (0.01, "passed"),
        (0.010001, "failed"),
    ],
)
def test_current_pipeline_error_rate_gate_enforces_ceiling(
    monkeypatch,
    error_rate,
    expected_status,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["runtime_metrics"]["error_rate"] = error_rate
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(
        gate
        for gate in report["gates"]
        if gate["name"] == "current_pipeline_error_rate"
    )
    assert gate["status"] == expected_status
    assert gate["observed"] == error_rate
    assert gate["threshold"] == 0.01


@pytest.mark.parametrize(
    ("section", "metric_name", "gate_name"),
    CURRENT_PIPELINE_NUMERIC_GATES,
)
def test_current_pipeline_numeric_gate_fails_when_metric_is_missing(
    monkeypatch,
    section,
    metric_name,
    gate_name,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report[section].pop(metric_name)
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(gate for gate in report["gates"] if gate["name"] == gate_name)
    assert gate["status"] == "failed"
    assert report["status"] == "failed"


@pytest.mark.parametrize("invalid_value", ["not-a-number", True])
@pytest.mark.parametrize(
    ("section", "metric_name", "gate_name"),
    CURRENT_PIPELINE_NUMERIC_GATES,
)
def test_current_pipeline_numeric_gate_fails_when_metric_is_not_numeric(
    monkeypatch,
    section,
    metric_name,
    gate_name,
    invalid_value,
):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report[section][metric_name] = invalid_value
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    gate = next(gate for gate in report["gates"] if gate["name"] == gate_name)
    assert gate["status"] == "failed"
    assert report["status"] == "failed"


def test_current_pipeline_gate_fails_when_no_cases_ran(monkeypatch):
    def current_pipeline(_dataset_dir, _collection):
        report = valid_current_pipeline_report()
        report["cases"] = []
        report["summary"] = {
            "case_count": 0,
            "error_count": 0,
            "empty_answer_count": 0,
        }
        return report

    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        current_pipeline,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
        raising=False,
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "current_pipeline_cases_present" in failed_gates


@pytest.mark.parametrize(
    ("violation", "failed_gate"),
    [
        ("reference_policy", "current_pipeline_generated_answers"),
        ("sqlite_backend", "current_pipeline_chroma_backend"),
        ("case_error", "current_pipeline_no_case_errors"),
        ("blank_answer", "current_pipeline_nonempty_answers"),
        ("evidence_fallback", "current_pipeline_generated_answers"),
        ("reference_fallback", "current_pipeline_no_reference_fallback"),
    ],
)
def test_current_pipeline_strict_gate_rejects_release_fallbacks(
    monkeypatch,
    violation,
    failed_gate,
):
    pipeline_report = copy.deepcopy(valid_current_pipeline_report())
    answer_policy = "generated"
    if violation == "reference_policy":
        answer_policy = "reference"
    elif violation == "sqlite_backend":
        pipeline_report["vector_store_backend"] = "SqliteVectorStore"
    elif violation == "case_error":
        pipeline_report["cases"][0]["error"] = "RuntimeError: query failed"
    elif violation == "blank_answer":
        pipeline_report["cases"][0]["answer"] = ""
    elif violation == "evidence_fallback":
        pipeline_report["cases"][0]["answer_source"] = "evidence_fallback"
    elif violation == "reference_fallback":
        pipeline_report["cases"][0]["answer_source"] = (
            "reference_answer_fallback"
        )

    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
        raising=False,
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy=answer_policy,
    )

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert failed_gate in failed_gates


def test_generated_policy_requires_current_pipeline():
    with pytest.raises(ValueError, match="requires current_pipeline"):
        run_acceptance(
            run_smoke=False,
            ragas_rounds=1,
            answer_policy="generated",
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"java_baseline_recall_at_1": float("nan")},
        {"java_baseline_mrr": -0.1},
        {"max_degradation": float("inf")},
        {"max_degradation": -0.01},
        {"max_p95_latency_ms": 0.0},
        {"max_fallback_rate": 1.01},
        {"max_error_rate": -0.01},
        {"min_recall_at_1": float("nan")},
    ],
)
def test_acceptance_rejects_non_finite_or_out_of_range_thresholds(overrides):
    with pytest.raises(ValueError, match="threshold"):
        run_acceptance(
            run_smoke=False,
            ragas_rounds=1,
            **overrides,
        )


def test_current_pipeline_gate_rejects_unjudged_low_quality_output(monkeypatch):
    pipeline_report = valid_current_pipeline_report()
    pipeline_report["cases"][0]["answer"] = "Totally unrelated output."
    pipeline_report["cases"][0]["retrieved_context_ids"] = []
    pipeline_report["cases"][0]["retrieved_contexts"] = []
    pipeline_report["retrieval_metrics"] = {"recall_at_1": 0.0, "mrr": 0.0}

    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: pipeline_report,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: {
            "status": "failed",
            "case_count": 1,
        },
        raising=False,
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "current_pipeline_recall_at_1" in failed_gates
    assert "current_pipeline_mrr" in failed_gates
    assert "current_pipeline_judged_answers" in failed_gates


def test_current_pipeline_release_status_ignores_static_harness_failure(monkeypatch):
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: valid_current_pipeline_report(),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        min_total_cases=999999,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "passed"
    assert report["release_gate_source"] == "current_pipeline_and_runtime_smoke"
    assert next(
        gate for gate in report["gates"] if gate["name"] == "ragas_total_cases"
    )["status"] == "failed"


def test_current_pipeline_release_status_keeps_canary_smoke_gate(monkeypatch):
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_smoke_canary",
        lambda _collection, *, require_chroma: (_ for _ in ()).throw(
            RuntimeError("smoke failed")
        ),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: valid_current_pipeline_report(),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "failed"
    assert next(
        gate for gate in report["gates"] if gate["name"] == "canary_smoke"
    )["status"] == "failed"


def test_static_harness_exception_does_not_block_current_release(monkeypatch):
    monkeypatch.setattr(
        "scripts.canary_acceptance._evaluate_ragas_round",
        lambda _dataset_dir, _round: (_ for _ in ()).throw(
            ValueError("legacy observation is invalid")
        ),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline",
        lambda _dataset_dir, _collection: valid_current_pipeline_report(),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance._run_current_pipeline_judge",
        lambda _dataset_dir, _pipeline_report: valid_current_pipeline_judge_report(),
    )

    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        current_pipeline=True,
        answer_policy="generated",
    )

    assert report["status"] == "passed"
    assert report["ragas"]["error"] == "ValueError: legacy observation is invalid"


def test_current_pipeline_judge_covers_every_generated_case(tmp_path, monkeypatch):
    captured = {}
    judge = object()
    monkeypatch.setattr(
        "scripts.canary_acceptance.load_judge_config",
        lambda: (object(), []),
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance.build_configured_judge",
        lambda _config: judge,
    )

    def load_cases(_dataset_dir, **kwargs):
        captured.update(kwargs)
        return [object()]

    monkeypatch.setattr(
        "scripts.canary_acceptance.load_answer_generation_cases",
        load_cases,
    )
    monkeypatch.setattr(
        "scripts.canary_acceptance.evaluate_judged_ragas",
        lambda cases, configured_judge: {
            "status": "passed",
            "case_count": len(cases),
            "judge_matches": configured_judge is judge,
        },
    )

    report = _run_current_pipeline_judge(tmp_path, valid_current_pipeline_report())

    assert captured["limit"] is None
    assert captured["answer_policy"] == "generated"
    assert report == {
        "status": "passed",
        "case_count": 1,
        "judge_matches": True,
    }
