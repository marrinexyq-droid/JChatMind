import sqlite3

import pytest

from src.core.query_engine import QueryEngine
from src.core.types import ChunkRecord, SearchRequest
from src.ingestion.integrity import FileIntegrityStore, ReindexRequiredError, sha256_file
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


class FailingReplacementSparseIndex(SqliteSparseIndex):
    def __init__(self, db_path):
        super().__init__(db_path)
        self.fail_next_delete = True

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise RuntimeError("old sparse delete failed")
        return super().delete_by_source_path(collection, source_path)


class FailingLoader:
    def load(self, source_path, collection):
        raise RuntimeError("document load failed")


class FailingSplitter:
    def split(self, document):
        raise RuntimeError("document split failed")


class FailingEmbeddingProvider(HashEmbeddingProvider):
    def embed_text(self, text: str) -> list[float]:
        raise RuntimeError("document embedding failed")


class PartiallyFailingVectorStore(SqliteVectorStore):
    def upsert_chunks(self, chunks, embeddings):
        super().upsert_chunks(chunks, embeddings)
        raise RuntimeError("dense upsert failed after a partial write")


class FailingDeleteSparseIndex(SqliteSparseIndex):
    def __init__(self, db_path):
        super().__init__(db_path)
        self.fail_delete = False

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        if self.fail_delete:
            raise RuntimeError("sparse delete failed")
        return super().delete_by_source_path(collection, source_path)


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
        history_db=tmp_path / "history.db",
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
    assert FileIntegrityStore(tmp_path / "history.db").has_dirty_index() is False

    response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
        history_db=tmp_path / "history.db",
    ).search(SearchRequest(query="New retrieval", collection="docs", top_k=1, mode="hybrid"))

    assert response.results
    assert "New retrieval" in response.results[0].text


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
    assert FileIntegrityStore(history_db).has_dirty_index() is False

    response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
        history_db=history_db,
    ).search(SearchRequest(query="Old retrieval", collection="docs", top_k=1, mode="hybrid"))

    assert response.results
    assert "Old retrieval" in response.results[0].text


@pytest.mark.parametrize("failure_stage", ("loader", "splitter", "embedding"))
def test_pre_write_failures_preserve_prior_success_and_record_only_new_failures(
    tmp_path, failure_stage
):
    source_a = tmp_path / "a.md"
    source_b = tmp_path / "b.md"
    failed_source = tmp_path / "new-failure.md"
    source_a.write_text("# A\n\nA old retrieval evidence.", encoding="utf-8")
    source_b.write_text("# B\n\nB retrieval evidence.", encoding="utf-8")
    failed_source.write_text("# New\n\nNew source failure.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    old_provider = HashEmbeddingProvider(dimensions=64)
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
    )
    assert pipeline.run(source_a, collection="docs").status == "ingested"
    assert pipeline.run(source_b, collection="docs").status == "ingested"
    old_digest = sha256_file(source_a)
    old_fingerprint = old_provider.compatibility_fingerprint()
    source_a.write_text("# A\n\nA changed retrieval evidence.", encoding="utf-8")

    failure_messages = {
        "loader": "document load failed",
        "splitter": "document split failed",
        "embedding": "document embedding failed",
    }
    failing_kwargs = {}
    failing_provider = old_provider
    if failure_stage == "loader":
        failing_kwargs["loader"] = FailingLoader()
    elif failure_stage == "splitter":
        failing_kwargs["splitter"] = FailingSplitter()
    else:
        failing_provider = FailingEmbeddingProvider(dimensions=64)
    with pytest.raises(RuntimeError, match=failure_messages[failure_stage]):
        IngestionPipeline(
            history_db=history_db,
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=failing_provider,
            **failing_kwargs,
        ).run(source_a, collection="docs")

    with pytest.raises(RuntimeError, match="document load failed"):
        IngestionPipeline(
            history_db=history_db,
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=old_provider,
            loader=FailingLoader(),
        ).run(failed_source, collection="docs")

    store = FileIntegrityStore(history_db)
    assert store.should_skip(source_a, "docs", old_digest, old_fingerprint)
    with sqlite3.connect(history_db) as conn:
        failed_status = conn.execute(
            "SELECT status FROM ingestion_history WHERE source_path = ? AND collection = ?",
            (str(failed_source), "docs"),
        ).fetchone()
    assert failed_status == ("failed",)

    assert pipeline.delete(source_b, collection="docs").status == "deleted"
    old_response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
        history_db=history_db,
    ).search(SearchRequest(query="A old retrieval", collection="docs", top_k=1, mode="hybrid"))
    assert old_response.results
    assert "A old retrieval" in old_response.results[0].text

    replacement_provider = StaticEmbeddingProvider(
        "provider=ollama;model=replacement;dimensions=3", [1.0, 0.0, 0.0]
    )
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        IngestionPipeline(
            history_db=history_db,
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=replacement_provider,
        ).run(source_a, collection="docs")
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        QueryEngine(
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=replacement_provider,
            history_db=history_db,
        ).search(SearchRequest(query="A old retrieval", collection="docs", top_k=1, mode="hybrid"))


def test_arm_contention_does_not_downgrade_the_winner_success_record(tmp_path, monkeypatch):
    source = tmp_path / "rag.md"
    source.write_text("# Old\n\nOld winner evidence.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    provider = HashEmbeddingProvider(dimensions=64)
    initial = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    assert initial.run(source, collection="docs").status == "ingested"
    old_digest = sha256_file(source)
    source.write_text("# Changed\n\nA contender must not erase the winner.", encoding="utf-8")

    contender = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    real_arm = contender.integrity_store.arm_index_dirty

    def lose_arm_ownership(*args, **kwargs):
        real_arm(*args, **kwargs)
        raise ReindexRequiredError("another ingestion owns the dirty marker")

    monkeypatch.setattr(contender.integrity_store, "arm_index_dirty", lose_arm_ownership)
    with pytest.raises(ReindexRequiredError, match="another ingestion owns"):
        contender.run(source, collection="docs")

    assert FileIntegrityStore(history_db).should_skip(
        source,
        "docs",
        old_digest,
        provider.compatibility_fingerprint(),
    )


@pytest.mark.parametrize("has_legacy_dirty_table", (False, True))
def test_legacy_failed_history_migration_gates_residual_indexes_until_global_cleanup(
    tmp_path, has_legacy_dirty_table
):
    source = tmp_path / "legacy.md"
    source.write_text("# Legacy\n\nResidual sparse and dense evidence.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=legacy;dimensions=2", [1.0, 0.0]
    )
    replacement_provider = StaticEmbeddingProvider(
        "provider=ollama;model=replacement;dimensions=3", [1.0, 0.0, 0.0]
    )
    with sqlite3.connect(history_db) as conn:
        conn.execute(
            """
            CREATE TABLE ingestion_history (
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
        conn.execute(
            """
            INSERT INTO ingestion_history (
                source_path, collection, sha256, embedding_fingerprint, status, document_id,
                chunk_count, error, updated_at
            ) VALUES (?, 'docs', ?, ?, 'failed', NULL, 0, 'old partial write',
                '2026-01-01T00:00:00+00:00')
            """,
            (str(source), sha256_file(source), old_provider.compatibility_fingerprint()),
        )
        if has_legacy_dirty_table:
            conn.execute(
                """
                CREATE TABLE local_index_integrity (
                    scope TEXT PRIMARY KEY,
                    embedding_fingerprint TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    error TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    residual_chunk = ChunkRecord(
        id="legacy-chunk",
        document_id="legacy-doc",
        collection="docs",
        text="Residual sparse and dense evidence.",
        metadata={"source_path": str(source)},
    )
    vector_store.upsert_chunks([residual_chunk], [old_provider.vector])
    sparse_index.upsert_chunks([residual_chunk])

    assert FileIntegrityStore(history_db).has_dirty_index() is True
    for provider in (old_provider, replacement_provider):
        for mode in ("vector", "hybrid"):
            with pytest.raises(ReindexRequiredError, match="re-index required"):
                QueryEngine(
                    vector_store=vector_store,
                    sparse_index=sparse_index,
                    embedding_provider=provider,
                    history_db=history_db,
                ).search(SearchRequest(query="Residual evidence", collection="docs", top_k=1, mode=mode))

    cleanup = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
    )
    assert cleanup.delete(source, collection="docs").status == "deleted"
    assert FileIntegrityStore(history_db).has_dirty_index() is False
    assert IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=replacement_provider,
    ).run(source, collection="docs").status == "ingested"


def test_delete_sparse_failure_gates_dense_and_hybrid_until_explicit_empty_cleanup(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Delete\n\nStale sparse evidence must be gated.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_path = tmp_path / "sparse.db"
    old_provider = StaticEmbeddingProvider(
        "provider=hash;model=old;dimensions=2", [1.0, 0.0]
    )
    replacement_provider = StaticEmbeddingProvider(
        "provider=ollama;model=replacement;dimensions=3", [1.0, 0.0, 0.0]
    )
    assert IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=SqliteSparseIndex(sparse_path),
        embedding_provider=old_provider,
    ).run(source, collection="docs").status == "ingested"

    failing_sparse = FailingDeleteSparseIndex(sparse_path)
    failing_sparse.fail_delete = True
    delete_pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=failing_sparse,
        embedding_provider=old_provider,
    )
    with pytest.raises(RuntimeError, match="sparse delete failed"):
        delete_pipeline.delete(source, collection="docs")

    assert vector_store.list_chunks("docs") == []
    assert failing_sparse.search("docs", "Stale sparse evidence", top_k=1)
    for mode in ("vector", "hybrid"):
        with pytest.raises(ReindexRequiredError, match="re-index required"):
            QueryEngine(
                vector_store=vector_store,
                sparse_index=failing_sparse,
                embedding_provider=old_provider,
                history_db=history_db,
            ).search(SearchRequest(query="Stale sparse evidence", collection="docs", top_k=1, mode=mode))

    for provider in (old_provider, replacement_provider):
        with pytest.raises(ReindexRequiredError, match="re-index required"):
            QueryEngine(
                sparse_index=failing_sparse,
                embedding_provider=provider,
                history_db=history_db,
            ).search(SearchRequest(query="Stale sparse evidence", collection="docs", top_k=1))
    with pytest.raises(ReindexRequiredError, match="history_db is required"):
        QueryEngine(sparse_index=failing_sparse, embedding_provider=old_provider)

    failing_sparse.fail_delete = False
    assert delete_pipeline.delete(source, collection="docs").status == "deleted"
    assert FileIntegrityStore(history_db).has_dirty_index() is False
    assert IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=failing_sparse,
        embedding_provider=replacement_provider,
    ).run(source, collection="docs").status == "ingested"


def test_successful_delete_of_one_of_many_sources_does_not_leave_a_dirty_gate(tmp_path):
    source_a = tmp_path / "a.md"
    source_b = tmp_path / "b.md"
    source_a.write_text("# A\n\nDelete this source.", encoding="utf-8")
    source_b.write_text("# B\n\nKeep this source queryable.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    provider = HashEmbeddingProvider(dimensions=64)
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    assert pipeline.run(source_a, collection="docs").status == "ingested"
    assert pipeline.run(source_b, collection="docs").status == "ingested"

    assert pipeline.delete(source_a, collection="docs").status == "deleted"
    assert FileIntegrityStore(history_db).has_dirty_index() is False
    response = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
        history_db=history_db,
    ).search(SearchRequest(query="Keep this source", collection="docs", top_k=1, mode="hybrid"))
    assert response.results
    assert "Keep this source" in response.results[0].text


def test_partial_dense_upsert_failure_rolls_back_current_source_chunks(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Atomicity\n\nPartial dense writes must be removed.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = PartiallyFailingVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    provider = HashEmbeddingProvider(dimensions=64)
    pipeline = IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )

    with pytest.raises(RuntimeError, match="dense upsert failed after a partial write"):
        pipeline.run(source, collection="docs")

    assert vector_store.list_chunks("docs") == []
    assert sparse_index.search("docs", "partial dense", top_k=1) == []
    with pytest.raises(ReindexRequiredError, match="re-index required"):
        QueryEngine(
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=provider,
            history_db=history_db,
        ).search(SearchRequest(query="partial dense", collection="docs", top_k=1, mode="vector"))


def test_replacement_sparse_delete_failure_blocks_every_dense_provider(tmp_path):
    source = tmp_path / "rag.md"
    source.write_text("# Old\n\nOld sparse evidence must not leak.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_path = tmp_path / "sparse.db"
    current_provider = StaticEmbeddingProvider(
        "provider=hash;model=current;dimensions=2", [1.0, 0.0]
    )
    other_provider = StaticEmbeddingProvider(
        "provider=ollama;model=other;dimensions=3", [1.0, 0.0, 0.0]
    )
    IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=SqliteSparseIndex(sparse_path),
        embedding_provider=current_provider,
    ).run(source, collection="docs")
    source.write_text("# New\n\nNew replacement evidence.", encoding="utf-8")

    failing_sparse = FailingReplacementSparseIndex(sparse_path)
    with pytest.raises(RuntimeError, match="old sparse delete failed"):
        IngestionPipeline(
            history_db=history_db,
            vector_store=vector_store,
            sparse_index=failing_sparse,
            embedding_provider=current_provider,
        ).run(source, collection="docs")

    assert vector_store.list_chunks("docs") == []
    assert failing_sparse.search("docs", "Old sparse evidence", top_k=1) == []
    for provider in (current_provider, other_provider):
        with pytest.raises(ReindexRequiredError, match="re-index required"):
            QueryEngine(
                vector_store=vector_store,
                sparse_index=failing_sparse,
                embedding_provider=provider,
                history_db=history_db,
            ).search(SearchRequest(query="Old sparse evidence", collection="docs", top_k=1))

    with pytest.raises(ReindexRequiredError, match="history_db is required"):
        QueryEngine(
            vector_store=vector_store,
            sparse_index=failing_sparse,
            embedding_provider=current_provider,
        ).search(SearchRequest(query="Old sparse evidence", collection="docs", top_k=1))


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

    with pytest.raises(ReindexRequiredError, match="re-index required"):
        QueryEngine(
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=old_provider,
            history_db=history_db,
        ).search(SearchRequest(query="dense sparse failure", collection="docs", top_k=1, mode="vector"))


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
