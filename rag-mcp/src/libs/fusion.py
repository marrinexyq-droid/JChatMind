from __future__ import annotations

from src.core.types import RetrievalResult


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    top_k: int,
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    scores: dict[str, float] = {}
    chosen: dict[str, RetrievalResult] = {}

    for ranked in ranked_lists:
        for rank, result in enumerate(ranked, start=1):
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            if result.chunk_id not in chosen or result.score > chosen[result.chunk_id].score:
                chosen[result.chunk_id] = result

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    fused: list[RetrievalResult] = []
    for chunk_id, score in ordered[:top_k]:
        result = chosen[chunk_id]
        fused.append(
            RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                text=result.text,
                score=score,
                source="hybrid",
                citation_id=result.citation_id,
                metadata=result.metadata,
            )
        )
    return fused
