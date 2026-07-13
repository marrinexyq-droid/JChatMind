from pathlib import Path

import pytest

from src.ingestion.loader_factory import load_document
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embeddings import HashEmbeddingProvider
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


def _write_single_page_pdf(path: Path, text: str) -> None:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    import fitz

    pdf = fitz.open()
    for text in page_texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def test_load_document_extracts_a_single_pdf_page(tmp_path):
    pdf_path = tmp_path / "evidence.pdf"
    _write_single_page_pdf(pdf_path, "JChatMind PDF evidence")

    document = load_document(pdf_path, "manuals")

    assert "JChatMind PDF evidence" in document.text
    assert document.text.startswith("<!-- page: 1 -->")
    assert document.metadata["file_suffix"] == ".pdf"
    assert document.metadata["page_count"] == 1


def test_load_document_supports_markdown_extensions_and_rejects_unknown_types(tmp_path):
    markdown_path = tmp_path / "note.markdown"
    unknown_path = tmp_path / "note.txt"
    markdown_path.write_text("# Markdown\n\nCompatible.", encoding="utf-8")
    unknown_path.write_text("unsupported", encoding="utf-8")

    document = load_document(markdown_path, "notes")

    assert document.text.startswith("# Markdown")
    assert document.metadata["file_suffix"] == ".markdown"
    with pytest.raises(ValueError, match=r"unsupported document type: \.txt"):
        load_document(unknown_path, "notes")


def test_pdf_ingestion_keeps_page_metadata_and_is_idempotent(tmp_path):
    pdf_path = tmp_path / "manual.pdf"
    _write_pdf(pdf_path, ["First PDF page", "Second PDF page"])
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )

    first = pipeline.run(pdf_path, collection="manuals")
    second = pipeline.run(pdf_path, collection="manuals")

    assert first.status == "ingested"
    assert second.status == "skipped"
    chunks = vector_store.list_chunks("manuals")
    assert [chunk.metadata["page"] for chunk in chunks] == [1, 2]
    assert [chunk.metadata["source_path"] for chunk in chunks] == [str(pdf_path), str(pdf_path)]
    assert all(chunk.metadata["sha256"] for chunk in chunks)
