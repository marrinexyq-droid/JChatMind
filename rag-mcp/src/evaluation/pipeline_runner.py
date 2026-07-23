from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from math import ceil, isfinite
from pathlib import Path
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.query_engine import QueryEngine
from src.core.types import RetrievalMode, SearchRequest
from src.evaluation.ragas_cases import load_jsonl


VERSION = "1.1"
COHORT_FINGERPRINT_VERSION = "pipeline-golden-v1"
RETRIEVAL_EVALUATOR_CONTRACT = {
    "name": "jchatmind-stable-context-retrieval",
    "version": "1.0",
    "match_basis": "ground_truth_context_ids",
    "recall_at_1": "matched_ground_truth_ids_at_rank_1/ground_truth_context_ids",
    "mrr": "reciprocal_rank_of_first_matched_ground_truth_context_id",
}
MATCH_METADATA_FIELDS = (
    "golden_context_id",
    "context_id",
    "source_path",
    "title",
    "heading",
)


@dataclass(frozen=True)
class PipelineCaseResult:
    case_id: str
    golden_case_sha256: str
    retrieved_context_ids: list[str]
    answer: str
    latency_ms: float
    ground_truth_context_ids: list[str]
    matched_ground_truth_context_ids: list[str | None]
    error: str | None = None
    retrieved_contexts: list[str] = field(default_factory=list)
    retrieved_results: list[dict[str, Any]] = field(default_factory=list)
    answer_source: str = "pipeline_error"


@dataclass(frozen=True)
class PipelineEvaluationReport:
    collection: str
    mode: RetrievalMode
    top_k: int
    vector_store_backend: str
    dataset: dict[str, Any]
    cases: list[PipelineCaseResult]


class PipelineGoldenCase(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, str_strip_whitespace=True)

    case_id: str = Field(min_length=8)
    dataset_split: str
    question: str = Field(min_length=5)
    answer: str
    reference_answer: str | None = None
    contexts: list[str]
    ground_truth: str = Field(min_length=20)
    reference_contexts: list[str]
    ground_truth_context_ids: list[str]
    collection: str
    tags: list[str]
    difficulty: Literal["easy", "medium", "hard"]
    expected_answer_type: str
    tactic: str
    source_refs: list[dict[str, Any]]
    quality: dict[str, Any]


class PipelineEvaluationRunner:
    def __init__(
        self,
        query_engine: QueryEngine,
        *,
        top_k: int = 5,
        mode: RetrievalMode = "hybrid",
    ) -> None:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        self.query_engine = query_engine
        self.top_k = top_k
        self.mode = mode

    def run(
        self,
        cases: Sequence[Mapping[str, Any]],
        collection: str,
    ) -> PipelineEvaluationReport:
        validated_cases = _validate_pipeline_cases(cases)
        dataset = _dataset_evidence(validated_cases)
        results: list[PipelineCaseResult] = []
        for case in validated_cases:
            case_id = case.case_id.strip()
            golden_case_sha256 = _golden_case_sha256(case)
            question = case.question.strip()
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
                matched_context_ids = [
                    _match_ground_truth_context(result, case)
                    for result in response.results
                ]
                results.append(
                    PipelineCaseResult(
                        case_id=case_id,
                        golden_case_sha256=golden_case_sha256,
                        retrieved_context_ids=[item.chunk_id for item in response.results],
                        retrieved_contexts=[item.text for item in response.results],
                        retrieved_results=[
                            {
                                "chunk_id": item.chunk_id,
                                "text": item.text,
                                "metadata": _retrieval_evidence_metadata(
                                    item.metadata
                                ),
                            }
                            for item in response.results
                        ],
                        answer=response.answer_text,
                        answer_source=response.answer_source,
                        ground_truth_context_ids=case.ground_truth_context_ids,
                        matched_ground_truth_context_ids=matched_context_ids,
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
                )
            except Exception as exc:
                results.append(
                    PipelineCaseResult(
                        case_id=case_id,
                        golden_case_sha256=golden_case_sha256,
                        retrieved_context_ids=[],
                        retrieved_contexts=[],
                        answer="",
                        ground_truth_context_ids=case.ground_truth_context_ids,
                        matched_ground_truth_context_ids=[],
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
            dataset=dataset,
            cases=results,
        )


def as_report_dict(report: PipelineEvaluationReport) -> dict[str, Any]:
    case_count = len(report.cases)
    error_count = sum(case.error is not None for case in report.cases)
    empty_answer_count = sum(not case.answer.strip() for case in report.cases)
    fallback_count = sum(
        case.answer_source != "generated_answer" for case in report.cases
    )
    recall_values = [
        _recall_at_one(
            case.ground_truth_context_ids,
            case.matched_ground_truth_context_ids,
        )
        for case in report.cases
    ]
    mrr_values = [
        _reciprocal_rank(case.matched_ground_truth_context_ids)
        for case in report.cases
    ]
    latency_values = sorted(round(case.latency_ms, 3) for case in report.cases)
    return {
        "version": VERSION,
        "status": (
            "passed"
            if case_count > 0 and error_count == 0 and empty_answer_count == 0
            else "failed"
        ),
        "collection": report.collection,
        "mode": report.mode,
        "top_k": report.top_k,
        "runtime_scope": "python_query_engine",
        "vector_store_backend": report.vector_store_backend,
        "dataset": report.dataset,
        "evaluator": dict(RETRIEVAL_EVALUATOR_CONTRACT),
        "summary": {
            "case_count": case_count,
            "error_count": error_count,
            "empty_answer_count": empty_answer_count,
        },
        "retrieval_metrics": {
            "recall_at_1": _mean(recall_values),
            "mrr": _mean(mrr_values),
        },
        "runtime_metrics": {
            "p95_latency_ms": _percentile_95(latency_values),
            "fallback_rate": _rate(fallback_count, case_count),
            "error_rate": _rate(error_count, case_count),
        },
        "cases": [
            {
                "case_id": case.case_id,
                "golden_case_sha256": case.golden_case_sha256,
                "ground_truth_context_ids": case.ground_truth_context_ids,
                "retrieved_context_ids": case.retrieved_context_ids,
                "matched_ground_truth_context_ids": (
                    case.matched_ground_truth_context_ids
                ),
                "retrieved_contexts": case.retrieved_contexts,
                "retrieved_results": case.retrieved_results,
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


def _validate_pipeline_cases(
    cases: Sequence[Mapping[str, Any]],
) -> list[PipelineGoldenCase]:
    validated: list[PipelineGoldenCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(cases):
        try:
            case = PipelineGoldenCase.model_validate(dict(raw_case))
        except (TypeError, ValueError, ValidationError) as exc:
            case_id = raw_case.get("case_id") if isinstance(raw_case, Mapping) else None
            label = str(case_id or f"index {index}")
            raise ValueError(f"invalid golden case {label}: {exc}") from exc
        if case.case_id in seen_ids:
            raise ValueError(f"invalid golden case {case.case_id}: duplicate case_id")
        seen_ids.add(case.case_id)
        validated.append(case)
    return validated


def _dataset_evidence(cases: Sequence[PipelineGoldenCase]) -> dict[str, Any]:
    semantic_cases = [_semantic_case_payload(case) for case in cases]
    return {
        "case_count": len(cases),
        "case_ids_sha256": _canonical_sha256(
            [case["case_id"] for case in semantic_cases],
            sort_keys=False,
        ),
        "cohort_sha256": _canonical_sha256(semantic_cases),
        "cohort_fingerprint_version": COHORT_FINGERPRINT_VERSION,
    }


def _golden_case_sha256(case: PipelineGoldenCase) -> str:
    return _canonical_sha256(_semantic_case_payload(case))


def _semantic_case_payload(case: PipelineGoldenCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id.strip(),
        "question": case.question.strip(),
        "ground_truth_context_ids": _normalize_semantic_value(
            case.ground_truth_context_ids
        ),
        "source_refs": _normalize_semantic_value(case.source_refs),
        "reference_contexts": _normalize_semantic_value(
            case.reference_contexts
        ),
        "ground_truth": case.ground_truth.strip(),
        "reference_answer": (
            case.reference_answer or case.ground_truth
        ).strip(),
    }


def _normalize_semantic_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_semantic_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_semantic_value(item) for item in value]
    return value


def _canonical_sha256(value: Any, *, sort_keys: bool = True) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _percentile_95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    index = max(0, ceil(0.95 * len(values)) - 1)
    return round(values[index], 3)


def _match_ground_truth_context(
    result: Any,
    case: PipelineGoldenCase,
) -> str | None:
    if result.chunk_id in case.ground_truth_context_ids:
        return result.chunk_id

    metadata = _retrieval_evidence_metadata(result.metadata)
    metadata_context_id = str(
        metadata.get("golden_context_id") or metadata.get("context_id") or ""
    )
    if metadata_context_id in case.ground_truth_context_ids:
        return metadata_context_id

    result_source_path = str(metadata.get("source_path") or "")
    result_heading = str(metadata.get("title") or metadata.get("heading") or "")
    for source_ref in case.source_refs:
        context_id = str(source_ref.get("context_id") or "")
        if context_id not in case.ground_truth_context_ids:
            continue
        expected_path = str(source_ref.get("source_path") or "")
        expected_heading = str(source_ref.get("heading") or "")
        if (
            expected_path
            and _source_path_matches(result_source_path, expected_path)
            and (
                not expected_heading
                or _normalized_text(result_heading)
                == _normalized_text(expected_heading)
            )
        ):
            return context_id

    for index, reference_context in enumerate(case.reference_contexts):
        if not _context_text_matches(str(result.text), reference_context):
            continue
        if index < len(case.ground_truth_context_ids):
            return case.ground_truth_context_ids[index]
        if len(case.ground_truth_context_ids) == 1:
            return case.ground_truth_context_ids[0]
    return None


def _source_path_matches(actual: str, expected: str) -> bool:
    normalized_actual = actual.replace("\\", "/").lower().strip()
    normalized_expected = expected.replace("\\", "/").lower().strip()
    return bool(normalized_expected) and (
        normalized_actual == normalized_expected
        or normalized_actual.endswith(f"/{normalized_expected}")
    )


def _retrieval_evidence_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    evidence: dict[str, Any] = {}
    for field_name in MATCH_METADATA_FIELDS:
        field_value = value.get(field_name)
        if isinstance(field_value, str):
            evidence[field_name] = field_value
        elif isinstance(field_value, (bool, int)):
            evidence[field_name] = field_value
        elif isinstance(field_value, float) and isfinite(field_value):
            evidence[field_name] = field_value
    return evidence


def _context_text_matches(actual: str, expected: str) -> bool:
    normalized_actual = _normalized_text(actual)
    normalized_expected = _normalized_text(expected)
    if min(len(normalized_actual), len(normalized_expected)) < 24:
        return False
    return (
        normalized_actual in normalized_expected
        or normalized_expected in normalized_actual
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _recall_at_one(
    ground_truth_ids: Sequence[str],
    matched_ids: Sequence[str | None],
) -> float:
    truth = set(ground_truth_ids)
    if not truth:
        return 0.0
    first_match = {matched_ids[0]} if matched_ids and matched_ids[0] else set()
    return len(first_match & truth) / len(truth)


def _reciprocal_rank(matched_ids: Sequence[str | None]) -> float:
    for index, context_id in enumerate(matched_ids, start=1):
        if context_id is not None:
            return 1.0 / index
    return 0.0
