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

    store = FileIntegrityStore(db_path)
    assert not store.should_skip(source, "notes", digest)

    store.mark_success(source, "notes", digest, document_id="doc1", chunk_count=2)

    assert store.should_skip(source, "notes", digest)
