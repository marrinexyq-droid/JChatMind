from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.ingestion.integrity import FileIntegrityStore, sha256_file
from src.ingestion.loaders import MarkdownLoader
from src.ingestion.splitter import MarkdownTextSplitter
from src.libs.embeddings import BaseEmbeddingProvider
from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import VectorStore


@dataclass(frozen=True)
class IngestionResult:
    status: str
    document_id: str | None
    chunk_count: int
    source_path: str
    collection: str
    message: str


@dataclass(frozen=True)
class DeleteResult:
    status: str
    source_path: str
    collection: str
    vector_chunks_deleted: int
    sparse_chunks_deleted: int
    history_deleted: bool
    message: str


class IngestionPipeline:
    def __init__(
        self,
        history_db: Path,
        vector_store: VectorStore,
        sparse_index: SqliteSparseIndex,
        embedding_provider: BaseEmbeddingProvider,
        loader: MarkdownLoader | None = None,
        splitter: MarkdownTextSplitter | None = None,
        trace_writer: JsonlTraceWriter | None = None,
    ):
        self.integrity_store = FileIntegrityStore(history_db)
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.embedding_provider = embedding_provider
        self.loader = loader or MarkdownLoader()
        self.splitter = splitter or MarkdownTextSplitter()
        self.trace_writer = trace_writer

    def run(self, source_path: Path, collection: str = "default") -> IngestionResult:
        trace = TraceContext(
            trace_type="ingestion",
            inputs={"source_path": str(source_path), "collection": collection},
        )
        digest = sha256_file(source_path)
        trace.record_stage(
            "file_integrity",
            method="sha256",
            details={"sha256": digest},
        )

        if self.integrity_store.should_skip(source_path, collection, digest):
            result = IngestionResult(
                status="skipped",
                document_id=None,
                chunk_count=0,
                source_path=str(source_path),
                collection=collection,
                message="unchanged file already ingested",
            )
            trace.record_stage("skip", method="ingestion_history", details={"reason": result.message})
            self._write_trace(trace)
            return result

        try:
            document = self.loader.load(source_path, collection)
            trace.record_stage(
                "load",
                method=self.loader.__class__.__name__,
                details={"document_id": document.id, "characters": len(document.text)},
            )
            chunks = self.splitter.split(document)
            trace.record_stage(
                "split",
                method=self.splitter.__class__.__name__,
                details={"chunk_count": len(chunks)},
            )
            embeddings = self.embedding_provider.embed_texts(
                [chunk.embedding_text() for chunk in chunks]
            )
            trace.record_stage(
                "embed",
                method=self.embedding_provider.__class__.__name__,
                details={"embedding_count": len(embeddings)},
            )
            self.vector_store.delete_by_source_path(collection, document.source_path)
            self.sparse_index.delete_by_source_path(collection, document.source_path)
            self.vector_store.upsert_chunks(chunks, embeddings)
            self.sparse_index.upsert_chunks(chunks)
            trace.record_stage(
                "upsert",
                method=self.vector_store.__class__.__name__,
                details={"chunk_count": len(chunks)},
            )
            self.integrity_store.mark_success(
                source_path,
                collection,
                digest,
                document_id=document.id,
                chunk_count=len(chunks),
            )
            result = IngestionResult(
                status="ingested",
                document_id=document.id,
                chunk_count=len(chunks),
                source_path=str(source_path),
                collection=collection,
                message="document ingested",
            )
            self._write_trace(trace)
            return result
        except Exception as exc:
            self.integrity_store.mark_failed(source_path, collection, digest, str(exc))
            self._write_trace(trace, error=str(exc))
            raise

    def delete(self, source_path: Path, collection: str = "default") -> DeleteResult:
        trace = TraceContext(
            trace_type="deletion",
            inputs={"source_path": str(source_path), "collection": collection},
        )
        vector_deleted = self.vector_store.delete_by_source_path(collection, str(source_path))
        sparse_deleted = self.sparse_index.delete_by_source_path(collection, str(source_path))
        history_deleted = self.integrity_store.delete(source_path, collection)
        trace.record_stage(
            "delete",
            method=self.vector_store.__class__.__name__,
            details={
                "vector_chunks_deleted": vector_deleted,
                "sparse_chunks_deleted": sparse_deleted,
                "history_deleted": history_deleted,
            },
        )
        status = "deleted" if vector_deleted or sparse_deleted or history_deleted else "not_found"
        result = DeleteResult(
            status=status,
            source_path=str(source_path),
            collection=collection,
            vector_chunks_deleted=vector_deleted,
            sparse_chunks_deleted=sparse_deleted,
            history_deleted=history_deleted,
            message="document index entries deleted" if status == "deleted" else "document not indexed",
        )
        self._write_trace(trace)
        return result

    def _write_trace(self, trace: TraceContext, error: str | None = None) -> None:
        if self.trace_writer is not None:
            self.trace_writer.write(trace.finish(error=error))
