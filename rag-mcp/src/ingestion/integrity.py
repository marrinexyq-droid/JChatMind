from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FileIntegrityStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def should_skip(self, source_path: Path, collection: str, sha256: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status FROM ingestion_history
                WHERE source_path = ? AND collection = ? AND sha256 = ?
                """,
                (str(source_path), collection, sha256),
            ).fetchone()
        return row is not None and row[0] == "success"

    def mark_success(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        document_id: str,
        chunk_count: int,
    ) -> None:
        self._upsert(source_path, collection, sha256, "success", document_id, chunk_count, None)

    def mark_failed(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        error: str,
    ) -> None:
        self._upsert(source_path, collection, sha256, "failed", None, 0, error)

    def delete(self, source_path: Path, collection: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM ingestion_history
                WHERE source_path = ? AND collection = ?
                """,
                (str(source_path), collection),
            )
        return cursor.rowcount > 0

    def _upsert(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        status: str,
        document_id: str | None,
        chunk_count: int,
        error: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_history (
                    source_path, collection, sha256, status, document_id,
                    chunk_count, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, collection) DO UPDATE SET
                    sha256 = excluded.sha256,
                    status = excluded.status,
                    document_id = excluded.document_id,
                    chunk_count = excluded.chunk_count,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    str(source_path),
                    collection,
                    sha256,
                    status,
                    document_id,
                    chunk_count,
                    error,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_history (
                    source_path TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    document_id TEXT,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_path, collection)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
