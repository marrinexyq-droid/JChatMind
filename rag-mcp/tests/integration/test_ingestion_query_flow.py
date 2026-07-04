from src.core.query_engine import QueryEngine
from src.core.types import SearchRequest
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embeddings import HashEmbeddingProvider
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


def test_ingestion_pipeline_skips_unchanged_and_query_returns_evidence(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text(
        "# Hybrid RAG\n\nHybrid retrieval combines dense vectors with BM25 keywords.",
        encoding="utf-8",
    )

    provider = HashEmbeddingProvider(dimensions=64)
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )

    first = pipeline.run(source, collection="docs")
    second = pipeline.run(source, collection="docs")

    assert first.status == "ingested"
    assert first.chunk_count >= 1
    assert second.status == "skipped"

    engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    response = engine.search(SearchRequest(query="BM25 keywords", collection="docs", top_k=3))

    assert response.results
    assert response.results[0].citation_id == "C1"
    assert "BM25" in response.answer_text


def test_reingesting_changed_file_replaces_old_chunks(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Old\n\nOld retrieval text.", encoding="utf-8")

    provider = HashEmbeddingProvider(dimensions=64)
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )

    pipeline.run(source, collection="docs")
    source.write_text("# New\n\nNew retrieval text.", encoding="utf-8")
    result = pipeline.run(source, collection="docs")

    chunks = vector_store.list_chunks("docs")
    assert result.status == "ingested"
    assert len(chunks) == 1
    assert "New retrieval" in chunks[0].text
    assert "Old retrieval" not in chunks[0].text


def test_deleting_ingested_file_removes_indexes_and_history(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Delete Me\n\nTemporary retrieval text.", encoding="utf-8")

    provider = HashEmbeddingProvider(dimensions=64)
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )

    pipeline.run(source, collection="docs")
    result = pipeline.delete(source, collection="docs")
    second = pipeline.delete(source, collection="docs")

    assert result.status == "deleted"
    assert result.vector_chunks_deleted == 1
    assert result.sparse_chunks_deleted == 1
    assert result.history_deleted is True
    assert second.status == "not_found"
    assert vector_store.list_chunks("docs") == []
    assert sparse_index.search("docs", "temporary retrieval", 3) == []
