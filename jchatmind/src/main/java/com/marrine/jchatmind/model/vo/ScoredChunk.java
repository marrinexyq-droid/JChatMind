package com.marrine.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 带相关度分数的检索结果
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ScoredChunk {
    private String id;
    private String kbId;
    private String docId;
    private String content;
    private String metadata;
    /** 检索来源: "vector", "bm25", "hybrid", "rerank" */
    private String source;
    /** 归一化后的分数 (0.0 ~ 1.0) */
    private double score;
}
