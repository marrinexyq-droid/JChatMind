from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.core.answer_generator import AnswerGenerator, EvidenceFallback, build_evidence_answer
from src.core.types import RetrievalResult, SearchRequest
from src.ingestion.integrity import FileIntegrityStore, ReindexRequiredError
from src.libs.embeddings import BaseEmbeddingProvider
from src.libs.fusion import reciprocal_rank_fusion
from src.libs.rerankers import BaseReranker
from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import VectorStore


AnswerSource = Literal["generated_answer", "evidence_fallback", "no_evidence"]


@dataclass(frozen=True)
class SearchResponse:
    answer_text: str
    results: list[RetrievalResult] = field(default_factory=list)
    answer_source: AnswerSource = "evidence_fallback"
    trace_id: str | None = None
    trace_stages: list[dict[str, Any]] = field(default_factory=list)


class QueryEngine:
    def __init__(
        self,
        vector_store: VectorStore | None = None,
        sparse_index: SqliteSparseIndex | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        history_db: Path | None = None,
        reranker: BaseReranker | None = None,
        trace_writer: JsonlTraceWriter | None = None,
        rrf_k: int = 60,
        candidate_pool_size: int = 20,
        answer_generator: AnswerGenerator | None = None,
    ):
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.embedding_provider = embedding_provider
        if (vector_store is not None or sparse_index is not None) and history_db is None:
            raise ReindexRequiredError(
                "history_db is required for local retrieval; re-index required to verify "
                "local index integrity"
            )
        self.integrity_store = FileIntegrityStore(history_db) if history_db is not None else None
        self.reranker = reranker
        self.trace_writer = trace_writer
        self.rrf_k = rrf_k
        self.candidate_pool_size = candidate_pool_size
        self.answer_generator = answer_generator

    def search(self, request: SearchRequest) -> SearchResponse:
        trace = TraceContext(
            trace_type="query",
            inputs={
                "query": request.query,
                "collection": request.collection,
                "top_k": request.top_k,
                "mode": request.mode,
            },
        )
        trace.record_stage(
            "query_processing",
            method="SearchRequest",
            details={"mode": request.mode, "top_k": request.top_k},
        )
        if not request.query.strip():
            return self._build_response(
                trace,
                answer_text="No evidence found.",
                results=[],
                answer_source="no_evidence",
            )

        retrieval_limit = request.top_k
        if request.mode == "hybrid-rerank":
            retrieval_limit = max(request.top_k, self.candidate_pool_size)

        dense: list[RetrievalResult] = []
        sparse: list[RetrievalResult] = []
        if self.vector_store is not None or self.sparse_index is not None:
            assert self.integrity_store is not None
            embedding_fingerprint = (
                self.embedding_provider.compatibility_fingerprint()
                if self.embedding_provider is not None
                else ""
            )
            self.integrity_store.require_collection_compatible(
                request.collection,
                embedding_fingerprint,
            )
        if self.vector_store is not None and self.embedding_provider is not None:
            self.vector_store.reset_if_empty(request.collection)
            query_embedding = self.embedding_provider.embed_text(request.query)
            dense = self.vector_store.similarity_search(
                request.collection,
                query_embedding,
                retrieval_limit,
            )
            trace.record_stage(
                "dense_retrieval",
                method=self.vector_store.__class__.__name__,
                details={
                    "count": len(dense),
                    "limit": retrieval_limit,
                    "results": _trace_results(dense),
                },
            )
        if self.sparse_index is not None and request.mode in {"hybrid", "hybrid-rerank"}:
            sparse = self.sparse_index.search(
                request.collection,
                request.query,
                retrieval_limit,
            )
            trace.record_stage(
                "sparse_retrieval",
                method=self.sparse_index.__class__.__name__,
                details={
                    "count": len(sparse),
                    "limit": retrieval_limit,
                    "results": _trace_results(sparse),
                },
            )

        if request.mode == "vector":
            results = dense[: request.top_k]
        elif dense and sparse:
            results = reciprocal_rank_fusion([dense, sparse], retrieval_limit, self.rrf_k)
            trace.record_stage(
                "fusion",
                method="reciprocal_rank_fusion",
                details={
                    "count": len(results),
                    "rrf_k": self.rrf_k,
                    "limit": retrieval_limit,
                    "results": _trace_results(results),
                },
            )
        else:
            results = (dense or sparse)[:retrieval_limit]

        if request.mode == "hybrid-rerank":
            if self.reranker is not None and results:
                candidate_count = len(results)
                try:
                    results = self.reranker.rerank(request.query, results, request.top_k)
                    trace.record_stage(
                        "rerank",
                        method=self.reranker.__class__.__name__,
                        details={
                            "candidate_count": candidate_count,
                            "selected_count": len(results),
                            "fallback": False,
                            "results": _trace_results(results),
                        },
                    )
                except Exception as exc:
                    trace.record_stage(
                        "rerank",
                        method=self.reranker.__class__.__name__,
                        details={
                            "candidate_count": candidate_count,
                            "selected_count": min(candidate_count, request.top_k),
                            "fallback": True,
                            "error": str(exc),
                            "results": _trace_results(results[: request.top_k]),
                        },
                    )
                    results = results[: request.top_k]
            elif self.reranker is None:
                candidate_count = len(results)
                results = results[: request.top_k]
                trace.record_stage(
                    "rerank",
                    method="not_configured",
                    details={
                        "candidate_count": candidate_count,
                        "selected_count": len(results),
                        "fallback": True,
                        "results": _trace_results(results),
                    },
                )
            else:
                results = results[: request.top_k]
                trace.record_stage(
                    "rerank",
                    method=self.reranker.__class__.__name__,
                    details={
                        "candidate_count": 0,
                        "selected_count": 0,
                        "fallback": False,
                        "results": [],
                    },
                )

        cited = [
            RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                text=result.text,
                score=result.score,
                source=result.source,
                citation_id=f"C{index}",
                metadata=result.metadata,
            )
            for index, result in enumerate(results, start=1)
        ]
        answer_text = _build_answer(cited)
        answer_source: AnswerSource = "evidence_fallback" if cited else "no_evidence"
        if cited and self.answer_generator is not None:
            try:
                generated_answer = self.answer_generator.generate(request.query, cited)
                fallback = isinstance(generated_answer, EvidenceFallback)
                answer_text = _build_answer(cited) if fallback else generated_answer
                answer_source = "evidence_fallback" if fallback else "generated_answer"
                details = {"fallback": fallback}
                if fallback:
                    details["reason"] = generated_answer.reason
                trace.record_stage(
                    "answer_generation",
                    method=self.answer_generator.__class__.__name__,
                    details=details,
                )
            except Exception:
                answer_text = _build_answer(cited)
                trace.record_stage(
                    "answer_generation",
                    method=self.answer_generator.__class__.__name__,
                    details={"fallback": True, "error": "answer generation failed"},
                )
        return self._build_response(
            trace,
            answer_text=answer_text,
            results=cited,
            answer_source=answer_source,
        )

    def _build_response(
        self,
        trace: TraceContext,
        *,
        answer_text: str,
        results: list[RetrievalResult],
        answer_source: AnswerSource,
    ) -> SearchResponse:
        trace.record_stage(
            "response_build",
            method="SearchResponse",
            details={
                "result_count": len(results),
                "answer_source": answer_source,
                "results": _trace_results(results),
            },
        )
        trace_payload = trace.finish()
        if self.trace_writer is not None:
            self.trace_writer.write(trace_payload)
        return SearchResponse(
            answer_text=answer_text,
            results=results,
            answer_source=answer_source,
            trace_id=trace.trace_id,
            trace_stages=_public_trace_stages(trace_payload["stages"]),
        )


def _build_answer(results: list[RetrievalResult]) -> str:
    return build_evidence_answer(results)


def _trace_results(results: list[RetrievalResult]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": result.chunk_id,
            "document_id": result.document_id,
            "score": round(result.score, 6),
            "source": result.source,
            "citation_id": result.citation_id,
        }
        for result in results
    ]


def _public_trace_stages(
    stages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    safe_detail_keys = {
        "mode",
        "top_k",
        "count",
        "limit",
        "rrf_k",
        "candidate_count",
        "selected_count",
        "fallback",
        "result_count",
        "answer_source",
        "results",
    }
    return [
        {
            "name": stage.get("name"),
            "method": stage.get("method"),
            "provider": stage.get("provider"),
            "details": {
                key: value
                for key, value in (stage.get("details") or {}).items()
                if key in safe_detail_keys
            },
            "elapsed_ms": stage.get("elapsed_ms"),
        }
        for stage in stages
    ]
