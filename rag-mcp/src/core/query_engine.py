from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.core.types import RetrievalResult, SearchRequest
from src.ingestion.integrity import FileIntegrityStore
from src.libs.embeddings import BaseEmbeddingProvider
from src.libs.fusion import reciprocal_rank_fusion
from src.libs.rerankers import BaseReranker
from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import VectorStore


@dataclass(frozen=True)
class SearchResponse:
    answer_text: str
    results: list[RetrievalResult] = field(default_factory=list)


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
    ):
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.embedding_provider = embedding_provider
        self.integrity_store = FileIntegrityStore(history_db) if history_db is not None else None
        self.reranker = reranker
        self.trace_writer = trace_writer
        self.rrf_k = rrf_k
        self.candidate_pool_size = candidate_pool_size

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
        if not request.query.strip():
            response = SearchResponse(answer_text="No evidence found.")
            self._write_trace(trace)
            return response

        retrieval_limit = request.top_k
        if request.mode == "hybrid-rerank":
            retrieval_limit = max(request.top_k, self.candidate_pool_size)

        dense: list[RetrievalResult] = []
        sparse: list[RetrievalResult] = []
        if self.vector_store is not None and self.embedding_provider is not None:
            if self.integrity_store is not None:
                self.integrity_store.require_collection_compatible(
                    request.collection,
                    self.embedding_provider.compatibility_fingerprint(),
                )
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
                details={"count": len(dense), "limit": retrieval_limit},
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
                details={"count": len(sparse), "limit": retrieval_limit},
            )

        if request.mode == "vector":
            results = dense[: request.top_k]
        elif dense and sparse:
            results = reciprocal_rank_fusion([dense, sparse], retrieval_limit, self.rrf_k)
            trace.record_stage(
                "fusion",
                method="reciprocal_rank_fusion",
                details={"count": len(results), "rrf_k": self.rrf_k, "limit": retrieval_limit},
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
                        },
                    )
                    results = results[: request.top_k]
            else:
                results = results[: request.top_k]

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
        response = SearchResponse(
            answer_text=_build_answer(cited),
            results=cited,
        )
        self._write_trace(trace)
        return response

    def _write_trace(self, trace: TraceContext) -> None:
        if self.trace_writer is not None:
            self.trace_writer.write(trace.finish())


def _build_answer(results: list[RetrievalResult]) -> str:
    if not results:
        return "No evidence found."
    lines = ["Evidence found:"]
    for result in results:
        citation = result.citation_id or "C?"
        snippet = " ".join(result.text.replace("\ufeff", "").split())
        lines.append(f"[{citation}] {snippet}")
    return "\n".join(lines)
