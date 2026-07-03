from __future__ import annotations

from dataclasses import dataclass, field

from src.core.types import RetrievalResult, SearchRequest


@dataclass(frozen=True)
class SearchResponse:
    answer_text: str
    results: list[RetrievalResult] = field(default_factory=list)


class QueryEngine:
    def search(self, request: SearchRequest) -> SearchResponse:
        if not request.query.strip():
            return SearchResponse(answer_text="No evidence found.")
        return SearchResponse(answer_text="No evidence found.")
