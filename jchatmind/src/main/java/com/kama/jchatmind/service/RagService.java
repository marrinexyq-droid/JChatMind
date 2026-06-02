package com.kama.jchatmind.service;

import com.kama.jchatmind.model.vo.ScoredChunk;

import java.util.List;

public interface RagService {
    float[] embed(String text);

    /** 纯向量检索（保留兼容） */
    List<String> similaritySearch(String kbId, String title);

    /** 混合检索：向量 + BM25 + RRF 融合 + Rerank
     *  @param mode "vector" | "hybrid" | "hybrid-rerank" */
    List<ScoredChunk> hybridSearch(String kbId, String query, int topK, String mode);

    /** 确保数据库索引存在（HNSW + TSV + GIN） */
    void ensureIndexes();
}
