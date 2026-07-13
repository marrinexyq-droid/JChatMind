from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.core.types import ChunkRecord, RetrievalResult


class SqliteSparseIndex:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        with self._connect() as conn:
            for chunk in chunks:
                conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk.id,))
                conn.execute(
                    """
                    INSERT INTO chunk_fts (
                        chunk_id, document_id, collection, text, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.collection,
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    ),
                )

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        deleted = 0
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, metadata_json
                FROM chunk_fts
                WHERE collection = ?
                """,
                (collection,),
            ).fetchall()
            for chunk_id, metadata_json in rows:
                metadata = _loads_json_object(metadata_json)
                if metadata.get("source_path") == source_path:
                    conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
                    deleted += 1
        return deleted

    def has_source_path(self, collection: str, source_path: str) -> bool:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metadata_json
                FROM chunk_fts
                WHERE collection = ?
                """,
                (collection,),
            ).fetchall()
        return any(
            _loads_json_object(metadata_json).get("source_path") == source_path
            for (metadata_json,) in rows
        )

    def is_empty(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM chunk_fts").fetchone()
        return row is not None and row[0] == 0

    def search(self, collection: str, query: str, top_k: int) -> list[RetrievalResult]:
        terms = _query_terms(query)
        if not terms:
            return []
        try:
            return self._fts_search(collection, terms, top_k)
        except sqlite3.OperationalError:
            return self._fallback_search(collection, terms, top_k)

    def _fts_search(
        self,
        collection: str,
        terms: list[str],
        top_k: int,
    ) -> list[RetrievalResult]:
        match_query = " OR ".join(terms)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, document_id, text, metadata_json, bm25(chunk_fts) AS rank
                FROM chunk_fts
                WHERE collection = ? AND chunk_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (collection, match_query, top_k),
            ).fetchall()
        return [
            RetrievalResult(
                chunk_id=chunk_id,
                document_id=document_id,
                text=text,
                score=-rank,
                source="sparse",
                metadata=_loads_json_object(metadata_json),
            )
            for chunk_id, document_id, text, metadata_json, rank in rows
        ]

    def _fallback_search(
        self,
        collection: str,
        terms: list[str],
        top_k: int,
    ) -> list[RetrievalResult]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, document_id, text, metadata_json
                FROM chunk_fts
                WHERE collection = ?
                """,
                (collection,),
            ).fetchall()
        results: list[RetrievalResult] = []
        for chunk_id, document_id, text, metadata_json in rows:
            lower = text.lower()
            score = sum(1 for term in terms if term in lower)
            if score:
                results.append(
                    RetrievalResult(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        text=text,
                        score=float(score),
                        source="sparse",
                        metadata=_loads_json_object(metadata_json),
                    )
                )
        return sorted(results, key=lambda item: (-item.score, item.chunk_id))[:top_k]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    collection UNINDEXED,
                    text,
                    metadata_json UNINDEXED
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _query_terms(query: str) -> list[str]:
    return re.findall(r"[\w]+", query.lower())


def _loads_json_object(value: str) -> dict[str, Any]:
    raw = json.loads(value)
    return raw if isinstance(raw, dict) else {}
