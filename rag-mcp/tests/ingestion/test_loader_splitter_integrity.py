import sqlite3
from pathlib import Path

from src.ingestion.integrity import FileIntegrityStore, sha256_file
from src.ingestion.loaders import MarkdownLoader
from src.ingestion.splitter import MarkdownTextSplitter


def test_markdown_loader_builds_document(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# RAG\n\nRetrieval augmented generation.", encoding="utf-8")

    document = MarkdownLoader().load(source, collection="notes")

    assert document.collection == "notes"
    assert document.source_path == str(source)
    assert document.metadata["file_name"] == "note.md"
    assert document.text.startswith("# RAG")


def test_markdown_loader_strips_utf8_bom(tmp_path):
    source = tmp_path / "note.md"
    source.write_bytes("# RAG\n\nBOM-safe text.".encode("utf-8-sig"))

    document = MarkdownLoader().load(source, collection="notes")

    assert not document.text.startswith("\ufeff")
    assert document.text.startswith("# RAG")


def test_splitter_creates_deterministic_heading_chunks(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# RAG\n\nDense retrieval.\n\n## Sparse\n\nBM25 search.", encoding="utf-8")
    document = MarkdownLoader().load(source, collection="notes")

    splitter = MarkdownTextSplitter(chunk_size=40, chunk_overlap=0)
    chunks = splitter.split(document)

    assert len(chunks) >= 2
    assert chunks[0].id == splitter.split(document)[0].id
    assert chunks[0].metadata["title"] == "RAG"
    assert chunks[0].metadata["chunk_index"] == 0


def test_integrity_store_detects_unchanged_successful_ingestion(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("same content", encoding="utf-8")
    db_path = tmp_path / "ingestion_history.db"
    digest = sha256_file(source)
    fingerprint = "provider=hash;model=hash;dimensions=128"

    store = FileIntegrityStore(db_path)
    assert not store.should_skip(source, "notes", digest, fingerprint)

    store.mark_success(
        source,
        "notes",
        digest,
        embedding_fingerprint=fingerprint,
        document_id="doc1",
        chunk_count=2,
    )

    assert store.should_skip(source, "notes", digest, fingerprint)
    assert not store.should_skip(source, "notes", digest, "provider=ollama;model=bge-m3")


def test_integrity_store_migrates_legacy_history_as_embedding_incompatible(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("same content", encoding="utf-8")
    db_path = tmp_path / "ingestion_history.db"
    digest = sha256_file(source)
    fingerprint = "provider=hash;model=hash;dimensions=128"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE ingestion_history (
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
        conn.execute(
            """
            INSERT INTO ingestion_history (
                source_path, collection, sha256, status, document_id, chunk_count, error, updated_at
            ) VALUES (?, ?, ?, 'success', 'doc1', 1, NULL, '2026-01-01T00:00:00+00:00')
            """,
            (str(source), "notes", digest),
        )

    store = FileIntegrityStore(db_path)

    assert not store.should_skip(source, "notes", digest, fingerprint)
    store.mark_success(source, "notes", digest, fingerprint, document_id="doc1", chunk_count=1)
    assert store.should_skip(source, "notes", digest, fingerprint)


def test_deleting_last_successful_document_removes_collection_fingerprint(tmp_path):
    source = tmp_path / "note.md"
    failed_source = tmp_path / "failed.md"
    source.write_text("same content", encoding="utf-8")
    failed_source.write_text("failed content", encoding="utf-8")
    store = FileIntegrityStore(tmp_path / "ingestion_history.db")
    legacy_fingerprint = "provider=hash;model=legacy;dimensions=128"

    store.mark_success(
        source,
        "notes",
        sha256_file(source),
        legacy_fingerprint,
        document_id="doc1",
        chunk_count=1,
    )
    store.mark_failed(
        failed_source,
        "notes",
        sha256_file(failed_source),
        legacy_fingerprint,
        "failed load",
    )
    assert store.delete(source, "notes") is True

    store.require_collection_compatible("notes", "provider=hash;model=replacement")
