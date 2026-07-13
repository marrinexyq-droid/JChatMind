from __future__ import annotations

import importlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from src.core.types import ChunkRecord, RetrievalResult


CHROMA_COLLECTION_NAME = "jchatmind_chunks"


class VectorStore(Protocol):
    def upsert_chunks(self, chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None:
        ...

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        ...

    def reset_if_empty(self, collection: str) -> bool:
        ...

    def similarity_search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalResult]:
        ...

    def list_chunks(self, collection: str | None = None) -> list[ChunkRecord]:
        ...

    def list_collections(self) -> list[str]:
        ...

    def collection_chunk_counts(self) -> dict[str, int]:
        ...

    def list_document_chunks(
        self,
        document_id: str,
        collection: str | None = None,
    ) -> list[ChunkRecord]:
        ...


class VectorStoreBackendUnavailable(RuntimeError):
    pass


class ChromaVectorStore:
    def __init__(self, persist_directory: Path):
        self.persist_directory = persist_directory
        try:
            chromadb = importlib.import_module("chromadb")
        except Exception as exc:
            raise VectorStoreBackendUnavailable(
                "chromadb is not installed; install rag-mcp[chroma] or enable "
                "sqlite_fallback_when_chroma_unavailable"
            ) from exc

        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_directory))
        self._collection = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        self._collection.upsert(
            ids=[_stored_chunk_id(chunk.collection, chunk.id) for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[_chroma_metadata(chunk) for chunk in chunks],
        )

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        chunk_ids = [
            _stored_chunk_id(collection, chunk.id)
            for chunk in self.list_chunks(collection)
            if chunk.metadata.get("source_path") == source_path
        ]
        if not chunk_ids:
            return 0
        self._collection.delete(ids=_with_legacy_ids(chunk_ids, collection))
        return len(chunk_ids)

    def reset_if_empty(self, collection: str) -> bool:
        if self._collection.count() != 0:
            return False
        self._client.delete_collection(name=CHROMA_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return True

    def similarity_search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalResult]:
        if top_k <= 0:
            return []
        response = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"collection": collection},
            include=["documents", "metadatas", "distances"],
        )
        ids = response.get("ids", [[]])[0]
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        results: list[RetrievalResult] = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            metadata = _loads_chroma_metadata(metadata)
            document_id = str(metadata.pop("_document_id", ""))
            row_collection = str(metadata.pop("_collection", collection))
            results.append(
                RetrievalResult(
                    chunk_id=_logical_chunk_id(row_collection, str(chunk_id)),
                    document_id=document_id,
                    text=str(text or ""),
                    score=_distance_to_score(distance),
                    source="vector",
                    metadata=_without_internal_metadata(metadata),
                )
            )
        return results

    def list_chunks(self, collection: str | None = None) -> list[ChunkRecord]:
        kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if collection is not None:
            kwargs["where"] = {"collection": collection}
        response = self._collection.get(**kwargs)
        ids = response.get("ids", [])
        documents = response.get("documents", [])
        metadatas = response.get("metadatas", [])
        chunks = [
            _chunk_from_chroma(str(chunk_id), str(text or ""), metadata)
            for chunk_id, text, metadata in zip(ids, documents, metadatas)
        ]
        return sorted(chunks, key=lambda item: (item.collection, item.document_id, item.id))

    def list_collections(self) -> list[str]:
        return sorted({chunk.collection for chunk in self.list_chunks()})

    def collection_chunk_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for chunk in self.list_chunks():
            counts[chunk.collection] = counts.get(chunk.collection, 0) + 1
        return dict(sorted(counts.items()))

    def list_document_chunks(
        self,
        document_id: str,
        collection: str | None = None,
    ) -> list[ChunkRecord]:
        chunks = [
            chunk
            for chunk in self.list_chunks(collection)
            if chunk.document_id == document_id
        ]
        return sorted(chunks, key=lambda item: (item.collection, item.document_id, item.id))


class SqliteVectorStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_chunks(self, chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, collection, text, embedding_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    document_id = excluded.document_id,
                    collection = excluded.collection,
                    text = excluded.text,
                    embedding_json = excluded.embedding_json,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        _stored_chunk_id(chunk.collection, chunk.id),
                        chunk.document_id,
                        chunk.collection,
                        chunk.text,
                        json.dumps(embedding),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        chunk_ids = [
            _stored_chunk_id(collection, chunk.id)
            for chunk in self.list_chunks(collection)
            if chunk.metadata.get("source_path") == source_path
        ]
        if not chunk_ids:
            return 0
        deletion_ids = _with_legacy_ids(chunk_ids, collection)
        placeholders = ",".join("?" for _ in deletion_ids)
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM chunks WHERE collection = ? AND chunk_id IN ({placeholders})",
                (collection, *deletion_ids),
            )
        return len(chunk_ids)

    def reset_if_empty(self, collection: str) -> bool:
        return False

    def similarity_search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalResult]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, document_id, text, embedding_json, metadata_json
                FROM chunks
                WHERE collection = ?
                """,
                (collection,),
            ).fetchall()

        scored: list[RetrievalResult] = []
        for chunk_id, document_id, text, embedding_json, metadata_json in rows:
            embedding = json.loads(embedding_json)
            scored.append(
                RetrievalResult(
                    chunk_id=_logical_chunk_id(collection, str(chunk_id)),
                    document_id=document_id,
                    text=text,
                    score=_cosine(query_embedding, embedding),
                    source="vector",
                    metadata=_loads_json_object(metadata_json),
                )
            )
        return sorted(scored, key=lambda item: (-item.score, item.chunk_id))[:top_k]

    def list_chunks(self, collection: str | None = None) -> list[ChunkRecord]:
        query = "SELECT chunk_id, document_id, collection, text, metadata_json FROM chunks"
        params: tuple[Any, ...] = ()
        if collection is not None:
            query += " WHERE collection = ?"
            params = (collection,)
        query += " ORDER BY collection, document_id, chunk_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            ChunkRecord(
                id=_logical_chunk_id(str(row_collection), str(chunk_id)),
                document_id=document_id,
                collection=row_collection,
                text=text,
                metadata=_loads_json_object(metadata_json),
            )
            for chunk_id, document_id, row_collection, text, metadata_json in rows
        ]

    def list_collections(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT collection FROM chunks ORDER BY collection"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def collection_chunk_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT collection, COUNT(*)
                FROM chunks
                GROUP BY collection
                ORDER BY collection
                """
            ).fetchall()
        return {str(collection): int(count) for collection, count in rows}

    def list_document_chunks(
        self,
        document_id: str,
        collection: str | None = None,
    ) -> list[ChunkRecord]:
        query = """
            SELECT chunk_id, document_id, collection, text, metadata_json
            FROM chunks
            WHERE document_id = ?
        """
        params: tuple[Any, ...] = (document_id,)
        if collection is not None:
            query += " AND collection = ?"
            params = (document_id, collection)
        query += " ORDER BY collection, document_id, chunk_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            ChunkRecord(
                id=_logical_chunk_id(str(row_collection), str(chunk_id)),
                document_id=row_document_id,
                collection=row_collection,
                text=text,
                metadata=_loads_json_object(metadata_json),
            )
            for chunk_id, row_document_id, row_collection, text, metadata_json in rows
        ]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_collection ON chunks(collection)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def build_vector_store(project_root: Path, storage_settings: Any) -> VectorStore:
    backend = str(getattr(storage_settings, "vector_store_backend", "chroma")).lower()
    if backend == "chroma":
        try:
            return ChromaVectorStore(project_root / storage_settings.chroma_path)
        except VectorStoreBackendUnavailable:
            if getattr(storage_settings, "sqlite_fallback_when_chroma_unavailable", False):
                return SqliteVectorStore(project_root / storage_settings.vector_store_db)
            raise
    if backend == "sqlite":
        return SqliteVectorStore(project_root / storage_settings.vector_store_db)
    raise ValueError(f"unsupported vector store backend: {backend}")


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _loads_json_object(value: str) -> dict[str, Any]:
    raw = json.loads(value)
    return raw if isinstance(raw, dict) else {}


def _chroma_metadata(chunk: ChunkRecord) -> dict[str, str]:
    metadata = dict(chunk.metadata)
    return {
        "collection": chunk.collection,
        "document_id": chunk.document_id,
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "source_path": str(metadata.get("source_path") or ""),
    }


def _stored_chunk_id(collection: str, chunk_id: str) -> str:
    return f"{collection}:{chunk_id}"


def _logical_chunk_id(collection: str, stored_chunk_id: str) -> str:
    prefix = f"{collection}:"
    if stored_chunk_id.startswith(prefix):
        return stored_chunk_id[len(prefix):]
    return stored_chunk_id


def _with_legacy_ids(stored_chunk_ids: list[str], collection: str) -> list[str]:
    ids = list(stored_chunk_ids)
    ids.extend(_logical_chunk_id(collection, chunk_id) for chunk_id in stored_chunk_ids)
    return sorted(set(ids))


def _loads_chroma_metadata(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    metadata = _loads_json_object(str(raw.get("metadata_json") or "{}"))
    metadata["_document_id"] = str(raw.get("document_id") or "")
    metadata["_collection"] = str(raw.get("collection") or "")
    return metadata


def _chunk_from_chroma(chunk_id: str, text: str, metadata: Any) -> ChunkRecord:
    loaded = _loads_chroma_metadata(metadata)
    document_id = str(loaded.pop("_document_id", ""))
    collection = str(loaded.pop("_collection", ""))
    return ChunkRecord(
        id=_logical_chunk_id(collection, chunk_id),
        document_id=document_id,
        collection=collection,
        text=text,
        metadata=loaded,
    )


def _distance_to_score(value: Any) -> float:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 1.0 - distance


def _without_internal_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if not key.startswith("_")
    }
