from __future__ import annotations

import hashlib
import sqlite3
import uuid
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

    def arm_index_dirty(
        self,
        source_path: Path,
        collection: str,
        embedding_fingerprint: str,
    ) -> str:
        operation_id = uuid.uuid4().hex
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO local_index_integrity (
                        scope, operation_id, embedding_fingerprint, source_path, collection, error,
                        updated_at
                    ) VALUES ('local', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        embedding_fingerprint,
                        str(source_path),
                        collection,
                        "replacement ingestion in progress",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ReindexRequiredError(
                "the local index is already being rebuilt or may contain residual vectors; "
                "re-index required: explicitly delete every document in the local index, "
                "then ingest all sources with the current embedding configuration"
            ) from exc
        return operation_id

    def record_dirty_index_failure(self, operation_id: str, error: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE local_index_integrity
                SET error = ?, updated_at = ?
                WHERE scope = 'local' AND operation_id = ?
                """,
                (
                    error,
                    datetime.now(timezone.utc).isoformat(),
                    operation_id,
                ),
            )
        if cursor.rowcount != 1:
            raise RuntimeError("the dirty-index marker is no longer owned by this ingestion")

    def has_dirty_index(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM local_index_integrity WHERE scope = 'local'"
            ).fetchone()
        return row is not None

    def clear_dirty_index_after_success(self, operation_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM local_index_integrity
                WHERE scope = 'local' AND operation_id = ?
                """,
                (operation_id,),
            )
        return cursor.rowcount == 1

    def clear_dirty_index_after_explicit_cleanup(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM local_index_integrity WHERE scope = 'local'")

    def require_collection_compatible(
        self,
        collection: str,
        embedding_fingerprint: str,
    ) -> None:
        with self._connect() as conn:
            dirty = conn.execute(
                """
                SELECT embedding_fingerprint, source_path, collection
                FROM local_index_integrity
                WHERE scope = 'local'
                """
            ).fetchone()
            if dirty is not None:
                raise ReindexRequiredError(
                    "the local index may contain residual vectors from a failed ingestion "
                    f"for collection '{dirty[2]}'; re-index required: explicitly delete every "
                    "document in the local index, then ingest all sources with the current "
                    "embedding configuration"
                )
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
                WHERE ingestion_history.status <> 'success' OR excluded.status = 'success'
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
            history_table_exists = _table_exists(conn, "ingestion_history")
            integrity_table_exists = _table_exists(conn, "local_index_integrity")
            integrity_columns_before_migration = (
                {
                    str(row[1])
                    for row in conn.execute("PRAGMA table_info(local_index_integrity)").fetchall()
                }
                if integrity_table_exists
                else set()
            )
            legacy_integrity_schema = history_table_exists and (
                not integrity_table_exists
                or "operation_id" not in integrity_columns_before_migration
            )
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS local_index_integrity (
                    scope TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    embedding_fingerprint TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    error TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            integrity_columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(local_index_integrity)").fetchall()
            }
            if "operation_id" not in integrity_columns:
                conn.execute(
                    "ALTER TABLE local_index_integrity "
                    "ADD COLUMN operation_id TEXT NOT NULL DEFAULT ''"
                )
            if legacy_integrity_schema:
                legacy_failed = conn.execute(
                    """
                    SELECT source_path, collection, embedding_fingerprint
                    FROM ingestion_history
                    WHERE status = 'failed'
                    ORDER BY updated_at, source_path, collection
                    LIMIT 1
                    """
                ).fetchone()
                if legacy_failed is not None:
                    conn.execute(
                        """
                        INSERT INTO local_index_integrity (
                            scope, operation_id, embedding_fingerprint, source_path, collection,
                            error, updated_at
                        ) VALUES ('local', '', ?, ?, ?, ?, ?)
                        ON CONFLICT(scope) DO NOTHING
                        """,
                        (
                            str(legacy_failed[2]),
                            str(legacy_failed[0]),
                            str(legacy_failed[1]),
                            "legacy failed ingestion may have left residual vectors",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )
