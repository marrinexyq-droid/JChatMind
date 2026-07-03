from src.core.types import RetrievalResult
from src.libs.embeddings import HashEmbeddingProvider
from src.libs.fusion import reciprocal_rank_fusion


def test_hash_embedding_is_deterministic_and_normalized():
    provider = HashEmbeddingProvider(dimensions=16)

    first = provider.embed_text("hybrid retrieval")
    second = provider.embed_text("hybrid retrieval")

    assert first == second
    assert len(first) == 16
    assert abs(sum(value * value for value in first) - 1.0) < 0.000001


def test_reciprocal_rank_fusion_merges_duplicate_chunks():
    dense = [
        RetrievalResult("a", "d1", "dense", 0.9, "vector"),
        RetrievalResult("b", "d1", "dense", 0.8, "vector"),
    ]
    sparse = [
        RetrievalResult("b", "d1", "sparse", 5.0, "sparse"),
        RetrievalResult("c", "d2", "sparse", 3.0, "sparse"),
    ]

    fused = reciprocal_rank_fusion([dense, sparse], top_k=3, rrf_k=60)

    assert [item.chunk_id for item in fused] == ["b", "a", "c"]
    assert fused[0].source == "hybrid"
