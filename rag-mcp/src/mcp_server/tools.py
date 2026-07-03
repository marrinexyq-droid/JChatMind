from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.query_engine import QueryEngine
from src.core.types import RetrievalMode, SearchRequest
from src.storage.vector_store import SqliteVectorStore


@dataclass(frozen=True)
class ToolPayload:
    text: str
    data: dict[str, Any]


class KnowledgeHub:
    def __init__(self, query_engine: QueryEngine, vector_store: SqliteVectorStore):
        self.query_engine = query_engine
        self.vector_store = vector_store

    def query_knowledge_hub(
        self,
        query: str,
        top_k: int = 5,
        collection: str = "default",
        mode: RetrievalMode = "hybrid",
    ) -> ToolPayload:
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")
        top_k = _positive_int(top_k, default=5)
        response = self.query_engine.search(
            SearchRequest(
                query=query,
                collection=collection or "default",
                top_k=top_k,
                mode=mode,
            )
        )
        citations = [
            {
                "citation_id": result.citation_id,
                "chunk_id": result.chunk_id,
                "document_id": result.document_id,
                "text": result.text,
                "score": round(result.score, 6),
                "source": result.source,
                "metadata": result.metadata,
            }
            for result in response.results
        ]
        return ToolPayload(
            text=response.answer_text,
            data={
                "answer": response.answer_text,
                "collection": collection or "default",
                "mode": mode,
                "result_count": len(response.results),
                "citations": citations,
            },
        )

    def list_collections(self) -> ToolPayload:
        collections = self.vector_store.list_collections()
        text = (
            "Collections:\n" + "\n".join(f"- {name}" for name in collections)
            if collections
            else "Collections: none"
        )
        return ToolPayload(text=text, data={"collections": collections})

    def get_document_summary(
        self,
        doc_id: str,
        collection: str | None = None,
        max_chars: int = 1200,
    ) -> ToolPayload:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("doc_id must not be empty")
        chunks = self.vector_store.list_document_chunks(doc_id, collection=collection)
        if not chunks:
            raise ValueError(f"document not found: {doc_id}")

        max_chars = _positive_int(max_chars, default=1200)
        metadata = chunks[0].metadata
        title = str(metadata.get("title") or metadata.get("file_name") or doc_id)
        preview = " ".join(chunk.text.strip() for chunk in chunks)
        preview = " ".join(preview.split())
        if len(preview) > max_chars:
            preview = _truncate(preview, max_chars)

        data = {
            "document_id": doc_id,
            "collection": chunks[0].collection,
            "chunk_count": len(chunks),
            "title": title,
            "source_path": metadata.get("source_path"),
            "preview": preview,
        }
        text = (
            f"Document: {title}\n"
            f"document_id={doc_id}\n"
            f"collection={chunks[0].collection}\n"
            f"chunk_count={len(chunks)}\n"
            f"source_path={metadata.get('source_path')}\n\n"
            f"{preview}"
        )
        return ToolPayload(text=text, data=data)


def _positive_int(value: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _truncate(value: str, max_chars: int) -> str:
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3].rstrip() + "..."
