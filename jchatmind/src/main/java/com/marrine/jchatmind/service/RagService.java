package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.ScoredChunk;

import java.util.List;

public interface RagService {
    float[] embed(String text);

    /** Pure vector retrieval, kept for compatibility. */
    List<String> similaritySearch(String kbId, String title);

    /**
     * Hybrid retrieval: vector + BM25 + RRF fusion + optional rerank.
     *
     * @param mode "vector" | "hybrid" | "hybrid-rerank"
     */
    List<ScoredChunk> hybridSearch(String kbId, String query, int topK, String mode);

    RagSearchResult hybridSearchWithTrace(String kbId, String query, int topK, String mode);

    RagSearchResult hybridSearchWithTrace(String kbId, QueryPlan queryPlan);

    /** Ensure database indexes exist (HNSW + TSV + GIN). */
    void ensureIndexes();
}
