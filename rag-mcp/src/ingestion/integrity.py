from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class ReindexRequiredError(RuntimeError):
    pass


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

    def should_skip(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        embedding_fingerprint: str,
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status FROM ingestion_history
                WHERE source_path = ? AND collection = ? AND sha256 = ?
                    AND embedding_fingerprint = ?
                """,
                (str(source_path), collection, sha256, embedding_fingerprint),
            ).fetchone()
        return row is not None and row[0] == "success"

    def mark_success(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        embedding_fingerprint: str,
        document_id: str,
        chunk_count: int,
    ) -> None:
        self._upsert(
            source_path,
            collection,
            sha256,
            embedding_fingerprint,
            "success",
            document_id,
            chunk_count,
            None,
        )

    def mark_failed(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        embedding_fingerprint: str,
        error: str,
    ) -> None:
        self._upsert(
            source_path,
            collection,
            sha256,
            embedding_fingerprint,
            "failed",
            None,
            0,
            error,
        )

    def delete(self, source_path: Path, collection: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM ingestion_history
                WHERE source_path = ? AND collection = ?
                """,
                (str(source_path), collection),
            )
            remaining = conn.execute(
                """
                SELECT COUNT(*) FROM ingestion_history
                WHERE collection = ? AND status = 'success'
                """,
                (collection,),
            ).fetchone()
            if remaining is not None and remaining[0] == 0:
                conn.execute(
                    "DELETE FROM collection_embedding_fingerprints WHERE collection = ?",
                    (collection,),
                )
        return cursor.rowcount > 0

    def require_collection_compatible(
        self,
        collection: str,
        embedding_fingerprint: str,
    ) -> None:
        with self._connect() as conn:
            fingerprints = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT DISTINCT embedding_fingerprint FROM ingestion_history
                    WHERE status = 'success'
                    """,
                ).fetchall()
            }
            fingerprints.update(
                str(row[0])
                for row in conn.execute(
                    "SELECT embedding_fingerprint FROM collection_embedding_fingerprints"
                ).fetchall()
            )
        if not fingerprints or fingerprints == {embedding_fingerprint}:
            return
        raise ReindexRequiredError(
            "embedding configuration is incompatible with the local index while "
            f"accessing collection '{collection}'; re-index required: delete every "
            "document in the local index, then ingest all sources with the current "
            "embedding configuration"
        )

    def _upsert(
        self,
        source_path: Path,
        collection: str,
        sha256: str,
        embedding_fingerprint: str,
        status: str,
        document_id: str | None,
        chunk_count: int,
        error: str | None,
    ) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_history (
                    source_path, collection, sha256, embedding_fingerprint, status, document_id,
                    chunk_count, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, collection) DO UPDATE SET
                    sha256 = excluded.sha256,
                    embedding_fingerprint = excluded.embedding_fingerprint,
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
                    embedding_fingerprint,
                    status,
                    document_id,
                    chunk_count,
                    error,
                    updated_at,
                ),
            )
            if status == "success":
                conn.execute(
                    """
                    INSERT INTO collection_embedding_fingerprints (
                        collection, embedding_fingerprint, updated_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(collection) DO UPDATE SET
                        embedding_fingerprint = excluded.embedding_fingerprint,
                        updated_at = excluded.updated_at
                    """,
                    (collection, embedding_fingerprint, updated_at),
                )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_history (
                    source_path TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    embedding_fingerprint TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    document_id TEXT,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_path, collection)
                )
                """
            )
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(ingestion_history)").fetchall()
            }
            if "embedding_fingerprint" not in columns:
                conn.execute(
                    "ALTER TABLE ingestion_history "
                    "ADD COLUMN embedding_fingerprint TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_embedding_fingerprints (
                    collection TEXT PRIMARY KEY,
                    embedding_fingerprint TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
