from __future__ import annotations

from dataclasses import dataclass, field

from src.core.types import RetrievalResult, SearchRequest
from src.libs.embeddings import BaseEmbeddingProvider
from src.libs.fusion import reciprocal_rank_fusion
from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


@dataclass(frozen=True)
class SearchResponse:
    answer_text: str
    results: list[RetrievalResult] = field(default_factory=list)


class QueryEngine:
    def __init__(
        self,
        vector_store: SqliteVectorStore | None = None,
        sparse_index: SqliteSparseIndex | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        trace_writer: JsonlTraceWriter | None = None,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.embedding_provider = embedding_provider
        self.trace_writer = trace_writer
        self.rrf_k = rrf_k

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

        dense: list[RetrievalResult] = []
        sparse: list[RetrievalResult] = []
        if self.vector_store is not None and self.embedding_provider is not None:
            query_embedding = self.embedding_provider.embed_text(request.query)
            dense = self.vector_store.similarity_search(
                request.collection,
                query_embedding,
                request.top_k,
            )
            trace.record_stage(
                "dense_retrieval",
                method=self.vector_store.__class__.__name__,
                details={"count": len(dense)},
            )
        if self.sparse_index is not None and request.mode in {"hybrid", "hybrid-rerank"}:
            sparse = self.sparse_index.search(request.collection, request.query, request.top_k)
            trace.record_stage(
                "sparse_retrieval",
                method=self.sparse_index.__class__.__name__,
                details={"count": len(sparse)},
            )

        if request.mode == "vector":
            results = dense[: request.top_k]
        elif dense and sparse:
            results = reciprocal_rank_fusion([dense, sparse], request.top_k, self.rrf_k)
            trace.record_stage(
                "fusion",
                method="reciprocal_rank_fusion",
                details={"count": len(results), "rrf_k": self.rrf_k},
            )
        else:
            results = (dense or sparse)[: request.top_k]

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
