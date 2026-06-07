package com.kama.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RagTrace {
    private String query;
    private String originalQuery;
    private String plannedQuery;
    private String queryType;
    private String kbId;
    private String mode;
    private Integer topK;
    private Integer candidatePoolSize;
    private Double vectorWeight;
    private Double bm25Weight;
    private Boolean rerankApplied;
    private Boolean rerankFallback;
    private Boolean selfRagApplied;
    private String selfRagDecision;
    private String selfRagReason;
    private Integer selfRagRetryCount;
    private List<RagTraceChunk> vectorResults;
    private List<RagTraceChunk> bm25Results;
    private List<RagTraceChunk> rrfResults;
    private List<RagTraceChunk> rerankResults;
    private List<RagTraceChunk> finalChunks;
}
