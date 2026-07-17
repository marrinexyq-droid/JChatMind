import copy
import json

import pytest

from scripts.canary_acceptance import _run_current_pipeline_judge, main, run_acceptance


def valid_current_pipeline_report():
    return {
        "status": "passed",
        "vector_store_backend": "ChromaVectorStore",
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
                "answer": "Live answer [C1].",
                "answer_source": "generated_answer",
                "retrieved_context_ids": ["chunk-1"],
                "retrieved_contexts": ["Live evidence."],
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


def test_run_acceptance_without_smoke_checks_stable_ragas(tmp_path):
    output_json = tmp_path / "acceptance.json"

    report = run_acceptance(
        output_json=output_json,
        run_smoke=False,
        ragas_rounds=2,
    )

    assert report["status"] == "passed"
    assert report["version"] == "2.7"
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
        "current_pipeline_mrr": "passed",
        "current_pipeline_judged_answers": "passed",
    }


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
