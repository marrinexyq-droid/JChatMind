from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RetrievalMode = Literal["vector", "hybrid", "hybrid-rerank"]


@dataclass(frozen=True)
class Document:
    id: str
    collection: str
    source_path: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    document_id: str
    collection: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def embedding_text(self) -> str:
        title = str(self.metadata.get("title", "")).strip()
        body = self.text.strip()
        return f"{title}\n{body}".strip() if title else body


@dataclass(frozen=True)
class SearchRequest:
    query: str
    collection: str = "default"
    top_k: int = 5
    mode: RetrievalMode = "hybrid"


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    citation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
