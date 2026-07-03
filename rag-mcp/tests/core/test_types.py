from src.core.types import ChunkRecord, Document, RetrievalResult, SearchRequest


def test_chunk_record_has_stable_text_for_embedding():
    chunk = ChunkRecord(
        id="doc1-0001-abc",
        document_id="doc1",
        collection="default",
        text="body",
        metadata={"title": "Heading"},
    )

    assert chunk.embedding_text() == "Heading\nbody"


def test_search_request_defaults():
    request = SearchRequest(query="What is RAG?")

    assert request.collection == "default"
    assert request.top_k == 5
    assert request.mode == "hybrid"


def test_retrieval_result_keeps_citation_id():
    result = RetrievalResult(
        chunk_id="c1",
        document_id="d1",
        text="evidence",
        score=0.9,
        source="hybrid",
        citation_id="C1",
    )

    assert result.citation_id == "C1"
