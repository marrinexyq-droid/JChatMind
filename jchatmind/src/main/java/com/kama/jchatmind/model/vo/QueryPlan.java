package com.kama.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryPlan {
    private String originalQuery;
    private String context;
    private String searchQuery;
    private QueryType queryType;
    private String mode;
    private Integer topK;
    private Integer candidatePoolSize;
    private Double vectorWeight;
    private Double bm25Weight;

    public String effectiveSearchQuery() {
        if (hasText(searchQuery)) {
            return searchQuery;
        }
        return hasText(originalQuery) ? originalQuery : "";
    }

    public int effectiveTopK() {
        return topK == null || topK <= 0 ? 5 : topK;
    }

    public int effectiveCandidatePoolSize() {
        return candidatePoolSize == null || candidatePoolSize <= 0 ? 20 : candidatePoolSize;
    }

    public double effectiveVectorWeight() {
        return vectorWeight == null || vectorWeight <= 0 ? 1.0 : vectorWeight;
    }

    public double effectiveBm25Weight() {
        return bm25Weight == null || bm25Weight <= 0 ? 1.0 : bm25Weight;
    }

    public String effectiveMode() {
        return hasText(mode) ? mode : "hybrid";
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
