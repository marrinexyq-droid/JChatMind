package com.marrine.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RagTraceChunk {
    private String citationId;
    private String id;
    private String kbId;
    private String docId;
    private String documentName;
    private String contentPreview;
    private String metadata;
    private List<String> matchedBy;
    private Integer vectorRank;
    private Double vectorScore;
    private Integer bm25Rank;
    private Double bm25Score;
    private Integer rrfRank;
    private Double rrfScore;
    private Integer graphRank;
    private Double graphScore;
    private Integer rerankRank;
    private Double rerankScore;
    private Integer finalRank;
}
