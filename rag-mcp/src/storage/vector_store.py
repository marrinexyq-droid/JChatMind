from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from src.core.types import ChunkRecord, RetrievalResult


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
                        chunk.id,
                        chunk.document_id,
                        chunk.collection,
                        chunk.text,
                        json.dumps(embedding),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )

    def delete_by_source_path(self, collection: str, source_path: str) -> None:
        chunk_ids = [
            chunk.id
            for chunk in self.list_chunks(collection)
            if chunk.metadata.get("source_path") == source_path
        ]
        if not chunk_ids:
            return
        placeholders = ",".join("?" for _ in chunk_ids)
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM chunks WHERE collection = ? AND chunk_id IN ({placeholders})",
                (collection, *chunk_ids),
            )

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
                    chunk_id=chunk_id,
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
                id=chunk_id,
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
                id=chunk_id,
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
