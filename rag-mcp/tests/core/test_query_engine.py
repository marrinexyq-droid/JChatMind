import json

import pytest

from src.core.answer_generator import AnswerGenerator
from src.core.query_engine import QueryEngine, _build_answer
from src.core.types import RetrievalResult, SearchRequest
from src.ingestion.integrity import ReindexRequiredError
from src.observability.trace_writer import JsonlTraceWriter


class FakeEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        return [1.0]

    def compatibility_fingerprint(self) -> str:
        return "provider=fake;model=test;dimensions=1"


class FakeVectorStore:
    def __init__(self, results: list[RetrievalResult]):
        self.results = results
        self.requested_top_k: int | None = None

    def similarity_search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalResult]:
        self.requested_top_k = top_k
        return self.results[:top_k]

    def reset_if_empty(self, collection: str) -> None:
        return None


class FakeSparseIndex:
    def __init__(self, results: list[RetrievalResult]):
        self.results = results
        self.requested_top_k: int | None = None

    def search(self, collection: str, query: str, top_k: int) -> list[RetrievalResult]:
        self.requested_top_k = top_k
        return self.results[:top_k]


class ReverseReranker:
    def __init__(self):
        self.candidate_ids: list[str] = []

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        self.candidate_ids = [candidate.chunk_id for candidate in candidates]
        selected = list(reversed(candidates))[:top_k]
        return [
            RetrievalResult(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                text=candidate.text,
                score=1.0 - (index * 0.1),
                source="rerank",
                metadata=candidate.metadata,
            )
            for index, candidate in enumerate(selected)
        ]


class FailingReranker:
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        raise RuntimeError("reranker unavailable")


class FixedLLM:
    def __init__(self, answer: str):
        self.answer = answer

    def generate(self, prompt: str) -> str:
        return self.answer


class FailingAnswerGenerator:
    def generate(self, query: str, evidence: list[RetrievalResult]) -> str:
        raise RuntimeError("OLLAMA_API_KEY=test-only-key")


def test_query_engine_empty_index_returns_no_evidence():
    engine = QueryEngine()
    response = engine.search(SearchRequest(query="missing"))

    assert response.results == []
    assert response.answer_text == "No evidence found."
    assert response.answer_source == "no_evidence"


def test_query_answer_strips_bom_from_legacy_chunks():
    answer = _build_answer(
        [
            RetrievalResult(
                chunk_id="c1",
                document_id="d1",
                text="\ufeff# Title\nBody",
                score=1.0,
                source="hybrid",
                citation_id="C1",
            )
        ]
    )

    assert "\ufeff" not in answer
    assert "[C1] # Title Body" in answer


def test_hybrid_rerank_expands_candidate_pool_and_uses_reranker(tmp_path):
    dense = [
        _result("c1", 0.9, "vector"),
        _result("c2", 0.8, "vector"),
        _result("c3", 0.7, "vector"),
        _result("c4", 0.6, "vector"),
    ]
    sparse = [
        _result("c1", 4.0, "sparse"),
        _result("c2", 3.0, "sparse"),
        _result("c3", 2.0, "sparse"),
        _result("c4", 1.0, "sparse"),
    ]
    vector_store = FakeVectorStore(dense)
    sparse_index = FakeSparseIndex(sparse)
    reranker = ReverseReranker()
    engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        reranker=reranker,
        candidate_pool_size=4,
    )

    response = engine.search(
        SearchRequest(
            query="rerank candidates",
            collection="war-room",
            top_k=2,
            mode="hybrid-rerank",
        )
    )

    assert vector_store.requested_top_k == 4
    assert sparse_index.requested_top_k == 4
    assert reranker.candidate_ids == ["c1", "c2", "c3", "c4"]
    assert [result.chunk_id for result in response.results] == ["c4", "c3"]
    assert [result.citation_id for result in response.results] == ["C1", "C2"]
    assert {result.source for result in response.results} == {"rerank"}


def test_hybrid_rerank_falls_back_to_fused_candidates_and_traces_error(tmp_path):
    trace_path = tmp_path / "traces.jsonl"
    engine = QueryEngine(
        vector_store=FakeVectorStore(
            [_result("c1", 0.9, "vector"), _result("c2", 0.8, "vector")]
        ),
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        reranker=FailingReranker(),
        trace_writer=JsonlTraceWriter(trace_path),
        candidate_pool_size=4,
    )

    response = engine.search(
        SearchRequest(
            query="rerank fallback",
            collection="war-room",
            top_k=1,
            mode="hybrid-rerank",
        )
    )

    assert [result.chunk_id for result in response.results] == ["c1"]
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    rerank_stage = next(stage for stage in trace["stages"] if stage["name"] == "rerank")
    assert rerank_stage["details"]["fallback"] is True
    assert rerank_stage["details"]["candidate_count"] == 2
    assert "reranker unavailable" in rerank_stage["details"]["error"]
    public_rerank_stage = next(
        stage for stage in response.trace_stages if stage["name"] == "rerank"
    )
    assert public_rerank_stage["details"]["fallback"] is True
    assert public_rerank_stage["details"]["results"][0]["chunk_id"] == "c1"
    assert "error" not in public_rerank_stage["details"]
    assert response.trace_id == trace["trace_id"]


def test_hybrid_rerank_traces_not_configured_as_real_fallback(tmp_path):
    engine = QueryEngine(
        vector_store=FakeVectorStore(
            [_result("c1", 0.9, "vector"), _result("c2", 0.8, "vector")]
        ),
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        reranker=None,
    )

    response = engine.search(
        SearchRequest(
            query="rerank without provider",
            collection="war-room",
            top_k=1,
            mode="hybrid-rerank",
        )
    )

    rerank_stage = next(
        stage for stage in response.trace_stages if stage["name"] == "rerank"
    )
    assert rerank_stage["method"] == "not_configured"
    assert rerank_stage["details"]["candidate_count"] == 2
    assert rerank_stage["details"]["selected_count"] == 1
    assert rerank_stage["details"]["fallback"] is True
    assert rerank_stage["details"]["results"][0]["chunk_id"] == "c1"


def test_query_engine_generates_cited_answer_and_traces_success(tmp_path):
    trace_path = tmp_path / "traces.jsonl"
    engine = QueryEngine(
        vector_store=FakeVectorStore([_result("c1", 0.9, "vector")]),
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        answer_generator=AnswerGenerator(FixedLLM("RRF combines ranked lists [C1].")),
        trace_writer=JsonlTraceWriter(trace_path),
    )

    response = engine.search(
        SearchRequest(query="What is RRF?", collection="war-room", top_k=1)
    )

    assert response.answer_text == "RRF combines ranked lists [C1]."
    assert response.answer_source == "generated_answer"
    assert [result.citation_id for result in response.results] == ["C1"]
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    answer_stage = next(stage for stage in trace["stages"] if stage["name"] == "answer_generation")
    assert answer_stage["details"]["fallback"] is False


def test_query_engine_falls_back_to_evidence_when_answer_generation_fails(tmp_path):
    trace_path = tmp_path / "traces.jsonl"
    engine = QueryEngine(
        vector_store=FakeVectorStore([_result("c1", 0.9, "vector")]),
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        answer_generator=FailingAnswerGenerator(),
        trace_writer=JsonlTraceWriter(trace_path),
    )

    response = engine.search(
        SearchRequest(query="What is RRF?", collection="war-room", top_k=1)
    )

    assert response.answer_text == "Evidence found:\n[C1] Text for c1"
    assert response.answer_source == "evidence_fallback"
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    answer_stage = next(stage for stage in trace["stages"] if stage["name"] == "answer_generation")
    assert answer_stage["details"]["fallback"] is True
    assert answer_stage["details"]["error"] == "answer generation failed"
    assert "test-only-key" not in json.dumps(trace)
    assert response.trace_id == trace["trace_id"]
    assert "test-only-key" not in json.dumps(response.trace_stages)
    public_answer_stage = next(
        stage for stage in response.trace_stages if stage["name"] == "answer_generation"
    )
    assert "error" not in public_answer_stage["details"]


def test_query_engine_traces_fallback_for_invalid_generated_citation(tmp_path):
    trace_path = tmp_path / "traces.jsonl"
    engine = QueryEngine(
        vector_store=FakeVectorStore([_result("c1", 0.9, "vector")]),
        embedding_provider=FakeEmbeddingProvider(),
        history_db=tmp_path / "history.db",
        answer_generator=AnswerGenerator(FixedLLM("RRF combines ranked lists [C9].")),
        trace_writer=JsonlTraceWriter(trace_path),
    )

    response = engine.search(
        SearchRequest(query="What is RRF?", collection="war-room", top_k=1)
    )

    assert response.answer_text == "Evidence found:\n[C1] Text for c1"
    assert response.answer_source == "evidence_fallback"
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    answer_stage = next(stage for stage in trace["stages"] if stage["name"] == "answer_generation")
    assert answer_stage["details"]["fallback"] is True
    assert answer_stage["details"]["reason"] == "invalid_citation"


def test_dense_retrieval_requires_an_integrity_store():
    vector_store = FakeVectorStore([_result("c1", 1.0, "vector")])
    with pytest.raises(ReindexRequiredError, match="history_db is required"):
        QueryEngine(
            vector_store=vector_store,
            embedding_provider=FakeEmbeddingProvider(),
        )

    assert vector_store.requested_top_k is None


def test_sparse_retrieval_requires_an_integrity_store():
    sparse_index = FakeSparseIndex([_result("c1", 1.0, "sparse")])

    with pytest.raises(ReindexRequiredError, match="history_db is required"):
        QueryEngine(sparse_index=sparse_index)

    assert sparse_index.requested_top_k is None


def _result(chunk_id: str, score: float, source: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        text=f"Text for {chunk_id}",
        score=score,
        source=source,
    )
