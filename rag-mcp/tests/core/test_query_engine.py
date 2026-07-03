from src.core.query_engine import QueryEngine, _build_answer
from src.core.types import RetrievalResult, SearchRequest


def test_query_engine_empty_index_returns_no_evidence():
    engine = QueryEngine()
    response = engine.search(SearchRequest(query="missing"))

    assert response.results == []
    assert response.answer_text == "No evidence found."


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
