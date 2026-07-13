import pytest

from src.core.query_engine import QueryEngine
from src.core.types import SearchRequest
from src.ingestion.integrity import ReindexRequiredError
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embeddings import BaseEmbeddingProvider, HashEmbeddingProvider
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import ChromaVectorStore, SqliteVectorStore


class StaticEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, fingerprint: str, vector: list[float]):
        self.fingerprint = fingerprint
        self.vector = vector

    def embed_text(self, text: str) -> list[float]:
        return self.vector

    def compatibility_fingerprint(self) -> str:
        return self.fingerprint


class FailingSparseIndex(SqliteSparseIndex):
    def __init__(self, db_path, fail_cleanup: bool = False):
        super().__init__(db_path)
        self.fail_cleanup = fail_cleanup
        self.fail_upsert = True
        self.upsert_failed = False

    def upsert_chunks(self, chunks):
        if not self.fail_upsert:
            return super().upsert_chunks(chunks)
        self.upsert_failed = True
        raise RuntimeError("sparse upsert failed")

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        if self.upsert_failed and self.fail_cleanup:
            raise RuntimeError("sparse rollback delete failed")
        return super().delete_by_source_path(collection, source_path)


class FailingLoader:
    def load(self, source_path, collection):
        raise RuntimeError("document load failed")


class PartiallyFailingVectorStore(SqliteVectorStore):
    def upsert_chunks(self, chunks, embeddings):
        super().upsert_chunks(chunks, embeddings)
        raise RuntimeError("dense upsert failed after a partial write")


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


def test_pre_write_failure_preserves_existing_successful_chunks(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Old\n\nOld retrieval text.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    provider = HashEmbeddingProvider(dimensions=64)
    IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    ).run(source, collection="docs")
    source.write_text("# New\n\nNew retrieval text.", encoding="utf-8")

    with pytest.raises(RuntimeError, match="document load failed"):
        IngestionPipeline(
            history_db=history_db,
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=provider,
            loader=FailingLoader(),
        ).run(source, collection="docs")

    chunks = vector_store.list_chunks("docs")
    assert len(chunks) == 1
    assert "Old retrieval" in chunks[0].text
    assert sparse_index.search("docs", "Old retrieval", top_k=1)


def test_partial_dense_upsert_failure_rolls_back_current_source_chunks(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Atomicity\n\nPartial dense writes must be removed.", encoding="utf-8")
    vector_store = PartiallyFailingVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )

    with pytest.raises(RuntimeError, match="dense upsert failed after a partial write"):
        pipeline.run(source, collection="docs")

    assert vector_store.list_chunks("docs") == []
    assert sparse_index.search("docs", "partial dense", top_k=1) == []


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


@pytest.mark.parametrize("backend", ("sqlite", "chroma"))
def test_sparse_upsert_failure_rolls_back_dense_chunks_and_prevents_old_dimension_zero_scores(
    tmp_path, backend
):
    source = tmp_path / "rag.md"
    source.write_text("# Atomicity\n\nThe dense write must not outlive a sparse failure.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    if backend == "chroma":
        pytest.importorskip("chromadb")
        vector_store = ChromaVectorStore(tmp_path / "chroma")
    else:
        vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = FailingSparseIndex(tmp_path / "sparse.db")
    current_provider = StaticEmbeddingProvider(
        "provider=ollama;model=current;dimensions=3", [1.0, 0.0, 0.0]
    )
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=old;dimensions=2", [1.0, 0.0]
    )
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=current_provider,
    )

    with pytest.raises(RuntimeError, match="sparse upsert failed"):
        pipeline.run(source, collection="docs")

    assert vector_store.list_chunks("docs") == []
    assert sparse_index.search("docs", "dense sparse failure", top_k=3) == []

    response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
        history_db=history_db,
    ).search(SearchRequest(query="dense sparse failure", collection="docs", top_k=1, mode="vector"))

    assert response.results == []


def test_failed_rollback_persists_a_dirty_index_gate_for_every_dense_provider(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Dirty Index\n\nRollback failure requires explicit reindexing.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = FailingSparseIndex(tmp_path / "sparse.db", fail_cleanup=True)
    current_provider = StaticEmbeddingProvider(
        "provider=ollama;model=current;dimensions=3", [1.0, 0.0, 0.0]
    )
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=old;dimensions=2", [1.0, 0.0]
    )
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=current_provider,
    )

    with pytest.raises(RuntimeError, match="sparse upsert failed"):
        pipeline.run(source, collection="docs")

    for provider in (current_provider, old_provider):
        engine = QueryEngine(
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=provider,
            history_db=history_db,
        )
        with pytest.raises(ReindexRequiredError, match="re-index required"):
            engine.search(SearchRequest(query="dirty", collection="docs", top_k=1, mode="vector"))


def test_explicit_delete_of_an_empty_dirty_index_allows_a_clean_rebuild(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Dirty Index\n\nExplicit deletion permits rebuilding.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = FailingSparseIndex(tmp_path / "sparse.db", fail_cleanup=True)
    provider = StaticEmbeddingProvider(
        "provider=ollama;model=current;dimensions=3", [1.0, 0.0, 0.0]
    )
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )

    with pytest.raises(RuntimeError, match="sparse upsert failed"):
        pipeline.run(source, collection="docs")

    sparse_index.fail_cleanup = False
    sparse_index.fail_upsert = False
    assert pipeline.delete(source, collection="docs").status == "deleted"
    assert pipeline.run(source, collection="docs").status == "ingested"


@pytest.mark.parametrize("backend", ("sqlite", "chroma"))
def test_embedding_fingerprint_change_blocks_reingestion_without_deleting_vectors(
    tmp_path, backend
):
    source = tmp_path / "rag.md"
    other_source = tmp_path / "other.md"
    source.write_text("# Compatibility\n\nEmbedding changes must replace stale vectors.", encoding="utf-8")
    other_source.write_text("# Other\n\nThis stale document must be cleared.", encoding="utf-8")

    if backend == "chroma":
        pytest.importorskip("chromadb")
        vector_store = ChromaVectorStore(tmp_path / "chroma")
    else:
        vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=legacy;dimensions=2", [1.0, 0.0]
    )
    new_provider = StaticEmbeddingProvider(
        "provider=ollama;model=bge-m3;dimensions=3", [0.0, 1.0, 0.0]
    )
    old_pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
    )
    new_pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=new_provider,
    )

    assert old_pipeline.run(source, collection="docs").status == "ingested"
    assert old_pipeline.run(other_source, collection="docs").status == "ingested"
    assert old_pipeline.run(source, collection="docs").status == "skipped"

    with pytest.raises(ReindexRequiredError, match="re-index required"):
        new_pipeline.run(source, collection="docs")

    engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=new_provider,
        history_db=tmp_path / "history.db",
    )
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        engine.search(SearchRequest(query="replacement vector", collection="docs", top_k=1, mode="vector"))

    chunks = vector_store.list_chunks("docs")
    assert len(chunks) == 2
    assert {chunk.metadata["source_path"] for chunk in chunks} == {str(source), str(other_source)}
    assert sparse_index.search("docs", "stale document", top_k=3)


def test_explicitly_deleted_chroma_collection_can_be_reindexed_with_new_dimensions(tmp_path):
    pytest.importorskip("chromadb")
    source = tmp_path / "rag.md"
    source.write_text("# Compatibility\n\nA clean collection can be reindexed.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = ChromaVectorStore(tmp_path / "chroma")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=legacy;dimensions=2", [1.0, 0.0]
    )
    new_provider = StaticEmbeddingProvider(
        "provider=ollama;model=bge-m3;dimensions=3", [0.0, 1.0, 0.0]
    )
    old_pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
    )
    new_pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=new_provider,
    )

    assert old_pipeline.run(source, collection="docs").status == "ingested"
    assert old_pipeline.delete(source, collection="docs").status == "deleted"
    empty_response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=new_provider,
        history_db=history_db,
    ).search(SearchRequest(query="reindexed", collection="docs", top_k=1, mode="vector"))
    assert empty_response.results == []
    assert new_pipeline.run(source, collection="docs").status == "ingested"

    response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=new_provider,
        history_db=history_db,
    ).search(SearchRequest(query="reindexed", collection="docs", top_k=1, mode="vector"))

    assert response.results[0].score == 1.0


@pytest.mark.parametrize("backend", ("sqlite", "chroma"))
def test_embedding_fingerprint_change_blocks_other_collections_in_same_local_index(tmp_path, backend):
    first_source = tmp_path / "first.md"
    second_source = tmp_path / "second.md"
    first_source.write_text("# First\n\nLegacy collection.", encoding="utf-8")
    second_source.write_text("# Second\n\nReplacement collection.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    if backend == "chroma":
        pytest.importorskip("chromadb")
        vector_store = ChromaVectorStore(tmp_path / "chroma")
    else:
        vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    legacy = StaticEmbeddingProvider("provider=hash;model=legacy;dimensions=2", [1.0, 0.0])
    replacement = StaticEmbeddingProvider(
        "provider=ollama;model=replacement;dimensions=3", [0.0, 1.0, 0.0]
    )
    legacy_pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=legacy,
    )
    replacement_pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=replacement,
    )

    assert legacy_pipeline.run(first_source, collection="first").status == "ingested"
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        replacement_pipeline.run(second_source, collection="second")

    replacement_engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=replacement,
        history_db=history_db,
    )
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        replacement_engine.search(
            SearchRequest(query="replacement", collection="second", top_k=1, mode="vector")
        )
    assert len(vector_store.list_chunks("first")) == 1
    assert vector_store.list_chunks("second") == []
    assert sparse_index.search("first", "legacy", top_k=3)
