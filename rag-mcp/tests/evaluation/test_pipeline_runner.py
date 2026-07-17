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


class RuntimeChunkIdQueryEngine(FakeQueryEngine):
    def search(self, request):
        self.requests.append(request)
        return SearchResponse(
            answer_text="Mapped current answer [C1].",
            answer_source="generated_answer",
            results=[
                RetrievalResult(
                    chunk_id="doc-0000-runtimehash",
                    document_id="doc",
                    text="Current pipeline evidence.",
                    score=0.9,
                    source="vector",
                    citation_id="C1",
                    metadata={
                        "source_path": "D:/knowledge/RAG-selfTest.md",
                        "title": "Relevant section",
                    },
                )
            ],
        )


def golden_case(
    case_id="answer-001",
    question="What does the live pipeline return?",
    **overrides,
):
    case = {
        "case_id": case_id,
        "dataset_split": "answer_generation",
        "question": question,
        "answer": "",
        "contexts": [],
        "ground_truth": "A sufficiently detailed expected answer for validation.",
        "reference_contexts": ["Current pipeline evidence."],
        "ground_truth_context_ids": ["chunk-live-1"],
        "collection": "live-evaluation",
        "tags": ["pipeline"],
        "difficulty": "easy",
        "expected_answer_type": "factoid",
        "tactic": "direct",
        "source_refs": [{"source": "test"}],
        "quality": {"source": "test"},
    }
    case.update(overrides)
    return case


def test_runner_queries_each_case_and_records_live_results():
    engine = FakeQueryEngine()
    runner = PipelineEvaluationRunner(engine, top_k=3, mode="hybrid")

    report = runner.run(
        [
            golden_case(
                reference_answer="This must never become the candidate answer.",
            )
        ],
        collection="live-evaluation",
    )

    assert [request.query for request in engine.requests] == [
        "What does the live pipeline return?"
    ]
    assert engine.requests[0].collection == "live-evaluation"
    assert engine.requests[0].top_k == 3
    assert engine.requests[0].mode == "hybrid"
    assert report.cases[0].case_id == "answer-001"
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
            golden_case("broken-01", "This query fails."),
            golden_case("healthy-01", "This query still runs."),
        ],
        collection="live-evaluation",
    )

    assert [request.query for request in engine.requests] == [
        "This query fails.",
        "This query still runs.",
    ]
    assert report.cases[0].case_id == "broken-01"
    assert report.cases[0].answer == ""
    assert report.cases[0].retrieved_context_ids == []
    assert report.cases[0].error == "RuntimeError: query failed"
    assert report.cases[1].case_id == "healthy-01"
    assert report.cases[1].answer == "Recovered answer."
    assert report.cases[1].error is None


def test_pipeline_report_is_separate_from_reference_dataset_answers():
    report = PipelineEvaluationRunner(FakeQueryEngine()).run(
        [
            golden_case(
                question="Use the current pipeline.",
                reference_answer="Static baseline answer.",
            )
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
    assert payload["retrieval_metrics"] == {"recall_at_1": 1.0, "mrr": 1.0}
    assert payload["runtime_metrics"]["fallback_rate"] == 0.0
    assert payload["runtime_metrics"]["error_rate"] == 0.0
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
        golden_case("answer-01", "First live question?"),
        {
            "case_id": "legacy-1",
            "dataset_split": "legacy_retrieval_observation",
            "question": "Static observation must not run.",
        },
        golden_case("answer-02", "Second live question?"),
    ]
    (dataset_dir / "ragas_cases.combined.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    cases = load_pipeline_cases(dataset_dir, limit=1)

    assert [case["case_id"] for case in cases] == ["answer-01"]


def test_current_pipeline_script_wiring_runs_loaded_cases(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "evaluation"
    dataset_dir.mkdir()
    (dataset_dir / "ragas_cases.combined.jsonl").write_text(
        json.dumps(
            golden_case("answer-01", "Run this through the live engine.")
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

    with pytest.raises(ValueError, match="invalid golden case"):
        runner.run([{"case_id": "broken"}], collection="live-evaluation")


def test_runner_validates_every_case_before_querying():
    engine = FakeQueryEngine()
    runner = PipelineEvaluationRunner(engine)

    with pytest.raises(ValueError, match="invalid golden case"):
        runner.run(
            [golden_case(), {"case_id": "broken"}],
            collection="live-evaluation",
        )

    assert engine.requests == []


def test_empty_pipeline_report_is_failed():
    report = PipelineEvaluationRunner(FakeQueryEngine()).run(
        [],
        collection="live-evaluation",
    )

    payload = as_report_dict(report)

    assert payload["status"] == "failed"
    assert payload["summary"]["case_count"] == 0


def test_runner_rejects_duplicate_case_ids_before_querying():
    engine = FakeQueryEngine()
    runner = PipelineEvaluationRunner(engine)

    with pytest.raises(ValueError, match="duplicate case_id"):
        runner.run(
            [
                golden_case(),
                golden_case(
                    case_id="answer-001 ",
                    question="A second valid question?",
                ),
            ],
            collection="live-evaluation",
        )

    assert engine.requests == []


def test_live_metrics_map_runtime_chunk_ids_to_stable_golden_contexts():
    case = golden_case(
        ground_truth_context_ids=["md:stable-section-id"],
        source_refs=[
            {
                "context_id": "md:stable-section-id",
                "source_path": "RAG-selfTest.md",
                "heading": "Relevant section",
            }
        ],
    )

    payload = as_report_dict(
        PipelineEvaluationRunner(RuntimeChunkIdQueryEngine()).run(
            [case],
            collection="live-evaluation",
        )
    )

    assert payload["cases"][0]["retrieved_context_ids"] == [
        "doc-0000-runtimehash"
    ]
    assert payload["cases"][0]["matched_ground_truth_context_ids"] == [
        "md:stable-section-id"
    ]
    assert payload["retrieval_metrics"] == {"recall_at_1": 1.0, "mrr": 1.0}
