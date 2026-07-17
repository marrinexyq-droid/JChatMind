import copy
import json

import pytest

from scripts.canary_acceptance import main, run_acceptance


def valid_current_pipeline_report():
    return {
        "status": "passed",
        "vector_store_backend": "ChromaVectorStore",
        "summary": {
            "case_count": 1,
            "error_count": 0,
            "empty_answer_count": 0,
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
        "current_pipeline_executed": "passed",
        "current_pipeline_generated_answers": "passed",
        "current_pipeline_cases_present": "passed",
        "current_pipeline_no_case_errors": "passed",
        "current_pipeline_nonempty_answers": "passed",
        "current_pipeline_no_reference_fallback": "passed",
        "current_pipeline_chroma_backend": "passed",
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
