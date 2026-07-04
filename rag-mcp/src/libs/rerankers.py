from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.types import RetrievalResult


class BaseReranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        ...


@dataclass(frozen=True)
class NoopReranker:
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        return candidates[:top_k]


@dataclass(frozen=True)
class HttpReranker:
    base_url: str = "http://127.0.0.1:8001"
    timeout_seconds: float = 8.0

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        if not candidates:
            return []
        payload = {
            "query": query,
            "documents": [candidate.text for candidate in candidates],
        }
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/rerank",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"reranker request failed: {exc}") from exc

        scores = _parse_scores(raw, candidate_count=len(candidates))
        if not scores:
            return candidates[:top_k]

        reranked: list[RetrievalResult] = []
        for index, score in scores[:top_k]:
            candidate = candidates[index]
            reranked.append(
                RetrievalResult(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    text=candidate.text,
                    score=score,
                    source="rerank",
                    citation_id=candidate.citation_id,
                    metadata=candidate.metadata,
                )
            )
        return reranked


def build_reranker(
    backend: str,
    base_url: str = "http://127.0.0.1:8001",
    timeout_seconds: float = 8.0,
) -> BaseReranker | None:
    normalized = backend.strip().lower()
    if normalized in {"", "none", "disabled"}:
        return None
    if normalized == "noop":
        return NoopReranker()
    if normalized in {"http", "local-http", "fastapi"}:
        return HttpReranker(base_url=base_url, timeout_seconds=timeout_seconds)
    raise ValueError(f"unsupported rerank backend: {backend}")


def _parse_scores(raw: Any, candidate_count: int) -> list[tuple[int, float]]:
    if not isinstance(raw, list):
        return []
    parsed: list[tuple[int, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("score")
        if not isinstance(index, int) or not isinstance(score, (int, float)):
            continue
        if 0 <= index < candidate_count:
            parsed.append((index, float(score)))
    return sorted(parsed, key=lambda item: (-item[1], item[0]))
