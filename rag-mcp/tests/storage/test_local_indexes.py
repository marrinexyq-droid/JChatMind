import sys
from types import ModuleType, SimpleNamespace

from src.core.types import ChunkRecord
from src.libs.embeddings import HashEmbeddingProvider
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import ChromaVectorStore, SqliteVectorStore, build_vector_store


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


def test_local_indexes_delete_by_source_path(tmp_path):
    provider = HashEmbeddingProvider(dimensions=32)
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    chunks = [
        ChunkRecord(
            "c1",
            "d1",
            "notes",
            "delete this chunk",
            metadata={"source_path": "a.md"},
        ),
        ChunkRecord(
            "c2",
            "d2",
            "notes",
            "keep this chunk",
            metadata={"source_path": "b.md"},
        ),
    ]

    vector_store.upsert_chunks(chunks, [provider.embed_text(chunk.text) for chunk in chunks])
    sparse_index.upsert_chunks(chunks)

    assert vector_store.delete_by_source_path("notes", "a.md") == 1
    assert sparse_index.delete_by_source_path("notes", "a.md") == 1
    assert [chunk.id for chunk in vector_store.list_chunks("notes")] == ["c2"]
    assert [result.chunk_id for result in sparse_index.search("notes", "keep", 3)] == ["c2"]


def test_sqlite_vector_store_scopes_physical_ids_by_collection(tmp_path):
    provider = HashEmbeddingProvider(dimensions=32)
    store = SqliteVectorStore(tmp_path / "vectors.db")
    chunks = [
        ChunkRecord("same-id", "doc", "alpha", "alpha retrieval", metadata={"source_path": "a.md"}),
        ChunkRecord("same-id", "doc", "beta", "beta retrieval", metadata={"source_path": "b.md"}),
    ]

    store.upsert_chunks(chunks, [provider.embed_text(chunk.text) for chunk in chunks])

    assert [chunk.id for chunk in store.list_chunks("alpha")] == ["same-id"]
    assert [chunk.id for chunk in store.list_chunks("beta")] == ["same-id"]
    assert store.similarity_search("alpha", provider.embed_text("alpha"), 1)[0].text == "alpha retrieval"
    assert store.similarity_search("beta", provider.embed_text("beta"), 1)[0].text == "beta retrieval"
    assert store.delete_by_source_path("alpha", "a.md") == 1
    assert store.list_chunks("alpha") == []
    assert [chunk.id for chunk in store.list_chunks("beta")] == ["same-id"]


def test_chroma_vector_store_uses_chromadb_contract(monkeypatch, tmp_path):
    chromadb = ModuleType("chromadb")
    chromadb.PersistentClient = FakeChromaClient
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)

    provider = HashEmbeddingProvider(dimensions=32)
    store = ChromaVectorStore(tmp_path / "chroma")
    chunks = [
        ChunkRecord(
            "c1",
            "d1",
            "notes",
            "hybrid retrieval and bm25",
            metadata={"source_path": "a.md"},
        ),
        ChunkRecord(
            "c2",
            "d2",
            "notes",
            "unrelated cooking recipe",
            metadata={"source_path": "b.md"},
        ),
    ]
    embeddings = [provider.embed_text(chunk.embedding_text()) for chunk in chunks]

    store.upsert_chunks(chunks, embeddings)
    results = store.similarity_search("notes", provider.embed_text("hybrid retrieval"), 1)

    assert results[0].chunk_id == "c1"
    assert results[0].source == "vector"
    assert store.list_collections() == ["notes"]
    assert store.collection_chunk_counts() == {"notes": 2}
    assert store.delete_by_source_path("notes", "a.md") == 1
    assert [chunk.id for chunk in store.list_chunks("notes")] == ["c2"]


def test_chroma_vector_store_scopes_physical_ids_by_collection(monkeypatch, tmp_path):
    chromadb = ModuleType("chromadb")
    chromadb.PersistentClient = FakeChromaClient
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)

    provider = HashEmbeddingProvider(dimensions=32)
    store = ChromaVectorStore(tmp_path / "chroma")
    chunks = [
        ChunkRecord("same-id", "doc", "alpha", "alpha retrieval", metadata={"source_path": "a.md"}),
        ChunkRecord("same-id", "doc", "beta", "beta retrieval", metadata={"source_path": "b.md"}),
    ]

    store.upsert_chunks(chunks, [provider.embed_text(chunk.text) for chunk in chunks])

    assert [chunk.id for chunk in store.list_chunks("alpha")] == ["same-id"]
    assert [chunk.id for chunk in store.list_chunks("beta")] == ["same-id"]
    assert store.similarity_search("alpha", provider.embed_text("alpha"), 1)[0].text == "alpha retrieval"
    assert store.similarity_search("beta", provider.embed_text("beta"), 1)[0].text == "beta retrieval"
    assert store.delete_by_source_path("alpha", "a.md") == 1
    assert store.list_chunks("alpha") == []
    assert [chunk.id for chunk in store.list_chunks("beta")] == ["same-id"]


def test_build_vector_store_falls_back_to_sqlite_when_chroma_missing(monkeypatch, tmp_path):
    from src.storage import vector_store as vector_store_module

    original_import_module = vector_store_module.importlib.import_module

    def fail_import(name: str):
        if name == "chromadb":
            raise ModuleNotFoundError(name)
        return original_import_module(name)

    monkeypatch.setattr(vector_store_module.importlib, "import_module", fail_import)
    settings = SimpleNamespace(
        vector_store_backend="chroma",
        sqlite_fallback_when_chroma_unavailable=True,
        chroma_path="data/db/chroma",
        vector_store_db="data/db/vector_store.db",
    )

    store = build_vector_store(tmp_path, settings)

    assert isinstance(store, SqliteVectorStore)


class FakeChromaClient:
    def __init__(self, path: str):
        self.path = path
        self.collection = FakeChromaCollection()

    def get_or_create_collection(self, name: str, metadata: dict):
        self.collection.name = name
        self.collection.metadata = metadata
        return self.collection


class FakeChromaCollection:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.name = ""
        self.metadata: dict = {}

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ):
        for chunk_id, embedding, document, metadata in zip(
            ids, embeddings, documents, metadatas
        ):
            self.rows[chunk_id] = {
                "embedding": embedding,
                "document": document,
                "metadata": metadata,
            }

    def delete(self, ids: list[str]):
        for chunk_id in ids:
            self.rows.pop(chunk_id, None)

    def get(self, include: list[str], where: dict | None = None):
        rows = self._filtered_rows(where)
        return {
            "ids": [chunk_id for chunk_id, _ in rows],
            "documents": [row["document"] for _, row in rows],
            "metadatas": [row["metadata"] for _, row in rows],
        }

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict,
        include: list[str],
    ):
        query_embedding = query_embeddings[0]
        rows = self._filtered_rows(where)
        scored = sorted(
            (
                (
                    1.0 - _cosine(query_embedding, row["embedding"]),
                    chunk_id,
                    row,
                )
                for chunk_id, row in rows
            ),
            key=lambda item: (item[0], item[1]),
        )[:n_results]
        return {
            "ids": [[chunk_id for _, chunk_id, _ in scored]],
            "documents": [[row["document"] for _, _, row in scored]],
            "metadatas": [[row["metadata"] for _, _, row in scored]],
            "distances": [[distance for distance, _, _ in scored]],
        }

    def _filtered_rows(self, where: dict | None):
        rows = sorted(self.rows.items())
        if not where:
            return rows
        return [
            (chunk_id, row)
            for chunk_id, row in rows
            if all(row["metadata"].get(key) == value for key, value in where.items())
        ]


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)
