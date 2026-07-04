from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.settings import Settings


@dataclass(frozen=True)
class CollectionSummary:
    name: str
    document_count: int
    chunk_count: int


@dataclass(frozen=True)
class DocumentSummary:
    document_id: str
    collection: str
    chunk_count: int
    source_path: str | None
    title: str | None


@dataclass(frozen=True)
class ChunkPreview:
    chunk_id: str
    document_id: str
    collection: str
    text_preview: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TraceRecord:
    line_number: int
    trace_id: str
    trace_type: str
    timestamp: str | None
    inputs: dict[str, Any]
    stages: list[dict[str, Any]]
    error: str | None


@dataclass(frozen=True)
class TraceInventory:
    total_count: int
    ingestion_count: int
    query_count: int
    malformed_count: int


@dataclass(frozen=True)
class EvaluationReport:
    path: Path
    total_cases: int | None
    split_counts: dict[str, int]
    retrieval_metric_count: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class DashboardOverview:
    collection_count: int
    document_count: int
    chunk_count: int
    trace_count: int
    ingestion_trace_count: int
    query_trace_count: int
    malformed_trace_rows: int
    latest_evaluation_report: str | None
    total_evaluation_cases: int | None


class DashboardService:
    def __init__(self, settings_path: Path):
        self.settings_path = settings_path.resolve()
        self.project_root = self.settings_path.parent.parent
        self.settings = Settings.load(self.settings_path)

    @classmethod
    def from_project_root(cls, project_root: Path) -> "DashboardService":
        return cls(project_root / "config" / "settings.yaml")

    def overview(self) -> DashboardOverview:
        collections = self.list_collections()
        trace_inventory = self.trace_inventory()
        evaluation_report = self.latest_evaluation_report()
        return DashboardOverview(
            collection_count=len(collections),
            document_count=sum(item.document_count for item in collections),
            chunk_count=sum(item.chunk_count for item in collections),
            trace_count=trace_inventory.total_count,
            ingestion_trace_count=trace_inventory.ingestion_count,
            query_trace_count=trace_inventory.query_count,
            malformed_trace_rows=trace_inventory.malformed_count,
            latest_evaluation_report=(
                evaluation_report.path.name if evaluation_report is not None else None
            ),
            total_evaluation_cases=(
                evaluation_report.total_cases if evaluation_report is not None else None
            ),
        )

    def list_collections(self) -> list[CollectionSummary]:
        db_path = self._resolve(self.settings.storage.vector_store_db)
        if not db_path.exists():
            return []
        with self._connect_readonly(db_path) as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT collection, COUNT(DISTINCT document_id), COUNT(*)
                    FROM chunks
                    GROUP BY collection
                    ORDER BY collection
                    """
                ).fetchall()
            except sqlite3.Error:
                return []
        return [
            CollectionSummary(
                name=str(collection),
                document_count=int(document_count),
                chunk_count=int(chunk_count),
            )
            for collection, document_count, chunk_count in rows
        ]

    def list_documents(self, collection: str | None = None) -> list[DocumentSummary]:
        db_path = self._resolve(self.settings.storage.vector_store_db)
        if not db_path.exists():
            return []
        query = """
            SELECT document_id, collection, COUNT(*), MIN(metadata_json)
            FROM chunks
        """
        params: tuple[Any, ...] = ()
        if collection is not None:
            query += " WHERE collection = ?"
            params = (collection,)
        query += " GROUP BY document_id, collection ORDER BY collection, document_id"
        with self._connect_readonly(db_path) as conn:
            try:
                rows = conn.execute(query, params).fetchall()
            except sqlite3.Error:
                return []
        documents: list[DocumentSummary] = []
        for document_id, row_collection, chunk_count, metadata_json in rows:
            metadata = _loads_json_object(metadata_json)
            documents.append(
                DocumentSummary(
                    document_id=str(document_id),
                    collection=str(row_collection),
                    chunk_count=int(chunk_count),
                    source_path=_string_or_none(metadata.get("source_path")),
                    title=_string_or_none(metadata.get("title")),
                )
            )
        return documents

    def list_chunks(
        self,
        collection: str | None = None,
        limit: int = 100,
    ) -> list[ChunkPreview]:
        db_path = self._resolve(self.settings.storage.vector_store_db)
        if not db_path.exists() or limit <= 0:
            return []
        query = """
            SELECT chunk_id, document_id, collection, text, metadata_json
            FROM chunks
        """
        params: tuple[Any, ...] = ()
        if collection is not None:
            query += " WHERE collection = ?"
            params = (collection,)
        query += " ORDER BY collection, document_id, chunk_id LIMIT ?"
        params = (*params, limit)
        with self._connect_readonly(db_path) as conn:
            try:
                rows = conn.execute(query, params).fetchall()
            except sqlite3.Error:
                return []
        return [
            ChunkPreview(
                chunk_id=str(chunk_id),
                document_id=str(document_id),
                collection=str(row_collection),
                text_preview=_preview_text(str(text)),
                metadata=_loads_json_object(metadata_json),
            )
            for chunk_id, document_id, row_collection, text, metadata_json in rows
        ]

    def list_traces(
        self,
        trace_type: str | None = None,
        limit: int = 100,
    ) -> list[TraceRecord]:
        records, _ = self._read_traces()
        if trace_type is not None:
            records = [record for record in records if record.trace_type == trace_type]
        if limit <= 0:
            return []
        return list(reversed(records))[:limit]

    def trace_inventory(self) -> TraceInventory:
        records, malformed_count = self._read_traces()
        return TraceInventory(
            total_count=len(records),
            ingestion_count=sum(1 for record in records if record.trace_type == "ingestion"),
            query_count=sum(1 for record in records if record.trace_type == "query"),
            malformed_count=malformed_count,
        )

    def latest_evaluation_report(self) -> EvaluationReport | None:
        metrics_dir = self._resolve(self.settings.evaluation.metrics_dir)
        if not metrics_dir.exists():
            return None
        candidates = sorted(
            (path for path in metrics_dir.glob("*.json") if path.is_file()),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        for path in candidates:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            inventory = raw.get("inventory")
            inventory = inventory if isinstance(inventory, dict) else {}
            split_counts = inventory.get("split_counts")
            retrieval_metrics = raw.get("retrieval_metrics")
            return EvaluationReport(
                path=path,
                total_cases=_int_or_none(inventory.get("total_cases")),
                split_counts={
                    str(key): int(value)
                    for key, value in (split_counts or {}).items()
                    if isinstance(value, int)
                }
                if isinstance(split_counts, dict)
                else {},
                retrieval_metric_count=(
                    len(retrieval_metrics) if isinstance(retrieval_metrics, list) else 0
                ),
                raw=raw,
            )
        return None

    def _read_traces(self) -> tuple[list[TraceRecord], int]:
        traces_path = self._resolve(self.settings.storage.traces_path)
        if not traces_path.exists():
            return [], 0
        records: list[TraceRecord] = []
        malformed_count = 0
        with traces_path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    malformed_count += 1
                    continue
                if not isinstance(raw, dict):
                    malformed_count += 1
                    continue
                records.append(
                    TraceRecord(
                        line_number=line_number,
                        trace_id=str(raw.get("trace_id") or ""),
                        trace_type=str(raw.get("trace_type") or ""),
                        timestamp=_string_or_none(raw.get("timestamp")),
                        inputs=_dict_or_empty(raw.get("inputs")),
                        stages=_list_of_dicts(raw.get("stages")),
                        error=_string_or_none(raw.get("error")),
                    )
                )
        return records, malformed_count

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.project_root / path

    @staticmethod
    def _connect_readonly(path: Path) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _preview_text(text: str, limit: int = 180) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None
