from src.core.query_engine import QueryEngine
from src.core.types import SearchRequest


def test_query_engine_empty_index_returns_no_evidence():
    engine = QueryEngine()
    response = engine.search(SearchRequest(query="missing"))

    assert response.results == []
    assert response.answer_text == "No evidence found."
