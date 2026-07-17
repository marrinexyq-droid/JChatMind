from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.core.query_engine import QueryEngine
from src.core.types import RetrievalMode, SearchRequest
from src.evaluation.ragas_cases import load_jsonl


VERSION = "1.0"


@dataclass(frozen=True)
class PipelineCaseResult:
    case_id: str
    retrieved_context_ids: list[str]
    answer: str
    latency_ms: float
    error: str | None = None
    retrieved_contexts: list[str] = field(default_factory=list)
    answer_source: str = "pipeline_error"


@dataclass(frozen=True)
class PipelineEvaluationReport:
    collection: str
    mode: RetrievalMode
    top_k: int
    vector_store_backend: str
    cases: list[PipelineCaseResult]


class PipelineEvaluationRunner:
    def __init__(
        self,
        query_engine: QueryEngine,
        *,
        top_k: int = 5,
        mode: RetrievalMode = "hybrid",
    ) -> None:
        self.query_engine = query_engine
        self.top_k = top_k
        self.mode = mode

    def run(
        self,
        cases: Sequence[Mapping[str, Any]],
        collection: str,
    ) -> PipelineEvaluationReport:
        results: list[PipelineCaseResult] = []
        for case in cases:
            case_id = str(case.get("case_id") or "").strip()
            if not case_id:
                raise ValueError("golden case is missing case_id")
            question = str(case.get("question") or "").strip()
            if not question:
                raise ValueError(f"case {case_id} is missing question")
            started = time.perf_counter()
            try:
                response = self.query_engine.search(
                    SearchRequest(
                        query=question,
                        collection=collection,
                        top_k=self.top_k,
                        mode=self.mode,
                    )
                )
                results.append(
                    PipelineCaseResult(
                        case_id=case_id,
                        retrieved_context_ids=[item.chunk_id for item in response.results],
                        retrieved_contexts=[item.text for item in response.results],
                        answer=response.answer_text,
                        answer_source=response.answer_source,
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
                )
            except Exception as exc:
                results.append(
                    PipelineCaseResult(
                        case_id=case_id,
                        retrieved_context_ids=[],
                        retrieved_contexts=[],
                        answer="",
                        latency_ms=(time.perf_counter() - started) * 1000,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        vector_store = getattr(self.query_engine, "vector_store", None)
        return PipelineEvaluationReport(
            collection=collection,
            mode=self.mode,
            top_k=self.top_k,
            vector_store_backend=(
                vector_store.__class__.__name__ if vector_store is not None else "unavailable"
            ),
            cases=results,
        )


def as_report_dict(report: PipelineEvaluationReport) -> dict[str, Any]:
    error_count = sum(case.error is not None for case in report.cases)
    empty_answer_count = sum(not case.answer.strip() for case in report.cases)
    return {
        "version": VERSION,
        "status": (
            "passed" if error_count == 0 and empty_answer_count == 0 else "failed"
        ),
        "collection": report.collection,
        "mode": report.mode,
        "top_k": report.top_k,
        "vector_store_backend": report.vector_store_backend,
        "summary": {
            "case_count": len(report.cases),
            "error_count": error_count,
            "empty_answer_count": empty_answer_count,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "retrieved_context_ids": case.retrieved_context_ids,
                "retrieved_contexts": case.retrieved_contexts,
                "answer": case.answer,
                "answer_source": case.answer_source,
                "latency_ms": round(case.latency_ms, 3),
                "error": case.error,
            }
            for case in report.cases
        ],
    }


def load_pipeline_cases(
    dataset_dir: Path,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and limit <= 0:
        return []
    rows = load_jsonl(dataset_dir / "ragas_cases.combined.jsonl")
    cases = [
        row
        for row in rows
        if row.get("dataset_split") == "answer_generation"
    ]
    return cases if limit is None else cases[:limit]
