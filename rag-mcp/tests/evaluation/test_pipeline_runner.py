import json
from types import SimpleNamespace

import pytest

from scripts.evaluate_current_pipeline import run_current_pipeline
from src.core.query_engine import SearchResponse
from src.core.types import RetrievalResult
from src.evaluation.pipeline_runner import (
    PipelineEvaluationRunner,
    as_report_dict,
    load_pipeline_cases,
)


class ChromaVectorStore:
    pass


class FakeQueryEngine:
    def __init__(self) -> None:
        self.requests = []
        self.vector_store = ChromaVectorStore()

    def search(self, request):
        self.requests.append(request)
        return SearchResponse(
            answer_text="Current pipeline answer [C1].",
            answer_source="generated_answer",
            results=[
                RetrievalResult(
                    chunk_id="chunk-live-1",
                    document_id="doc-1",
                    text="Current pipeline evidence.",
                    score=0.9,
                    source="vector",
                    citation_id="C1",
                )
            ],
        )


class FailingThenSuccessfulQueryEngine(FakeQueryEngine):
    def search(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            raise RuntimeError("query failed")
        return SearchResponse(answer_text="Recovered answer.")


def test_runner_queries_each_case_and_records_live_results():
    engine = FakeQueryEngine()
    runner = PipelineEvaluationRunner(engine, top_k=3, mode="hybrid")

    report = runner.run(
        [
            {
                "case_id": "case-1",
                "question": "What does the live pipeline return?",
                "reference_answer": "This must never become the candidate answer.",
            }
        ],
        collection="live-evaluation",
    )

    assert [request.query for request in engine.requests] == [
        "What does the live pipeline return?"
    ]
    assert engine.requests[0].collection == "live-evaluation"
    assert engine.requests[0].top_k == 3
    assert engine.requests[0].mode == "hybrid"
    assert report.cases[0].case_id == "case-1"
    assert report.cases[0].retrieved_context_ids == ["chunk-live-1"]
    assert report.cases[0].retrieved_contexts == ["Current pipeline evidence."]
    assert report.cases[0].answer == "Current pipeline answer [C1]."
    assert report.cases[0].answer_source == "generated_answer"
    assert report.cases[0].error is None
    assert report.cases[0].latency_ms >= 0


def test_runner_records_case_errors_and_continues_evaluation():
    engine = FailingThenSuccessfulQueryEngine()
    runner = PipelineEvaluationRunner(engine)

    report = runner.run(
        [
            {"case_id": "broken", "question": "This query fails."},
            {"case_id": "healthy", "question": "This query still runs."},
        ],
        collection="live-evaluation",
    )

    assert [request.query for request in engine.requests] == [
        "This query fails.",
        "This query still runs.",
    ]
    assert report.cases[0].case_id == "broken"
    assert report.cases[0].answer == ""
    assert report.cases[0].retrieved_context_ids == []
    assert report.cases[0].error == "RuntimeError: query failed"
    assert report.cases[1].case_id == "healthy"
    assert report.cases[1].answer == "Recovered answer."
    assert report.cases[1].error is None


def test_pipeline_report_is_separate_from_reference_dataset_answers():
    report = PipelineEvaluationRunner(FakeQueryEngine()).run(
        [
            {
                "case_id": "case-1",
                "question": "Use the current pipeline.",
                "reference_answer": "Static baseline answer.",
            }
        ],
        collection="live-evaluation",
    )

    payload = as_report_dict(report)

    assert payload["status"] == "passed"
    assert payload["vector_store_backend"] == "ChromaVectorStore"
    assert payload["summary"] == {
        "case_count": 1,
        "error_count": 0,
        "empty_answer_count": 0,
    }
    assert payload["cases"][0]["answer"] == "Current pipeline answer [C1]."
    assert payload["cases"][0]["answer_source"] == "generated_answer"
    assert payload["cases"][0]["retrieved_context_ids"] == ["chunk-live-1"]
    assert payload["cases"][0]["retrieved_contexts"] == [
        "Current pipeline evidence."
    ]
    assert "reference_answer" not in payload["cases"][0]


def test_pipeline_case_loader_selects_answer_generation_rows(tmp_path):
    dataset_dir = tmp_path / "evaluation"
    dataset_dir.mkdir()
    rows = [
        {
            "case_id": "answer-1",
            "dataset_split": "answer_generation",
            "question": "First live question?",
        },
        {
            "case_id": "legacy-1",
            "dataset_split": "legacy_retrieval_observation",
            "question": "Static observation must not run.",
        },
        {
            "case_id": "answer-2",
            "dataset_split": "answer_generation",
            "question": "Second live question?",
        },
    ]
    (dataset_dir / "ragas_cases.combined.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    cases = load_pipeline_cases(dataset_dir, limit=1)

    assert [case["case_id"] for case in cases] == ["answer-1"]


def test_current_pipeline_script_wiring_runs_loaded_cases(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "evaluation"
    dataset_dir.mkdir()
    (dataset_dir / "ragas_cases.combined.jsonl").write_text(
        json.dumps(
            {
                "case_id": "answer-1",
                "dataset_split": "answer_generation",
                "question": "Run this through the live engine.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    engine = FakeQueryEngine()
    monkeypatch.setattr(
        "scripts.evaluate_current_pipeline.build_local_hub",
        lambda _project_root: SimpleNamespace(query_engine=engine),
    )

    report = run_current_pipeline(
        project_root=tmp_path,
        dataset_dir=dataset_dir,
        collection="live-evaluation",
    )

    assert [request.query for request in engine.requests] == [
        "Run this through the live engine."
    ]
    assert report["status"] == "passed"
    assert report["cases"][0]["answer_source"] == "generated_answer"


def test_runner_fails_fast_for_invalid_golden_case_schema():
    runner = PipelineEvaluationRunner(FakeQueryEngine())

    with pytest.raises(ValueError, match="case broken is missing question"):
        runner.run([{"case_id": "broken"}], collection="live-evaluation")
