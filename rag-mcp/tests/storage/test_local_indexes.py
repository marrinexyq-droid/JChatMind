from src.core.types import ChunkRecord
from src.libs.embeddings import HashEmbeddingProvider
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


def test_sqlite_vector_store_returns_similar_chunk(tmp_path):
    provider = HashEmbeddingProvider(dimensions=32)
    store = SqliteVectorStore(tmp_path / "vectors.db")
    chunks = [
        ChunkRecord("c1", "d1", "notes", "hybrid retrieval and bm25"),
        ChunkRecord("c2", "d2", "notes", "unrelated cooking recipe"),
    ]
    embeddings = [provider.embed_text(chunk.embedding_text()) for chunk in chunks]

    store.upsert_chunks(chunks, embeddings)
    results = store.similarity_search("notes", provider.embed_text("hybrid retrieval"), 1)

    assert results[0].chunk_id == "c1"
    assert results[0].source == "vector"


def test_sqlite_sparse_index_returns_keyword_match(tmp_path):
    index = SqliteSparseIndex(tmp_path / "sparse.db")
    chunks = [
        ChunkRecord("c1", "d1", "notes", "dense vectors"),
        ChunkRecord("c2", "d2", "notes", "bm25 keyword search"),
    ]

    index.upsert_chunks(chunks)
    results = index.search("notes", "keyword search", 1)

    assert results[0].chunk_id == "c2"
    assert results[0].source == "sparse"
