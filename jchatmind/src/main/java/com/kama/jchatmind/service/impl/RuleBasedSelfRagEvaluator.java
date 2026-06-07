package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.QueryType;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.model.vo.SelfRagDecision;
import com.kama.jchatmind.model.vo.SelfRagEvaluation;
import com.kama.jchatmind.service.SelfRagEvaluator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
public class RuleBasedSelfRagEvaluator implements SelfRagEvaluator {

    private static final String MODE_HYBRID_RERANK = "hybrid-rerank";

    private final boolean enabled;
    private final int minFinalChunks;
    private final Double minRerankScore;
    private final int maxRetries;

    public RuleBasedSelfRagEvaluator(
            @Value("${rag.self-rag.enabled:true}") boolean enabled,
            @Value("${rag.self-rag.min-final-chunks:2}") int minFinalChunks,
            @Value("${rag.self-rag.min-rerank-score:#{null}}") Double minRerankScore,
            @Value("${rag.self-rag.max-retries:1}") int maxRetries) {
        this.enabled = enabled;
        this.minFinalChunks = Math.max(1, minFinalChunks);
        this.minRerankScore = minRerankScore;
        this.maxRetries = Math.max(0, maxRetries);
    }

    @Override
    public SelfRagEvaluation evaluate(QueryPlan queryPlan, RagSearchResult searchResult, int retryCount) {
        if (!enabled) {
            return decision(false, SelfRagDecision.ACCEPT, "Self-RAG disabled.");
        }

        QueryPlan plan = queryPlan == null ? QueryPlan.builder().build() : queryPlan;
        List<ScoredChunk> chunks = searchResult == null || searchResult.getChunks() == null
                ? List.of()
                : searchResult.getChunks();

        if (chunks.isEmpty()) {
            return decision(true, SelfRagDecision.INSUFFICIENT_EVIDENCE, "No retrieved evidence chunks.");
        }

        int requiredChunks = requiredChunks(plan);
        if (chunks.size() < requiredChunks) {
            if (!canRetry(retryCount)) {
                return decision(true, SelfRagDecision.INSUFFICIENT_EVIDENCE,
                        "Retrieved chunks below required evidence threshold after retry.");
            }
            if (!MODE_HYBRID_RERANK.equals(plan.effectiveMode())) {
                return decision(true, SelfRagDecision.RETRY_WITH_RERANK,
                        "Retrieved chunks below required evidence threshold; retry with rerank.");
            }
            return decision(true, SelfRagDecision.RETRY_WITH_LARGER_POOL,
                    "Reranked evidence is still sparse; retry with a larger candidate pool.");
        }

        if (rerankScoreTooLow(plan, chunks)) {
            if (!canRetry(retryCount)) {
                return decision(true, SelfRagDecision.INSUFFICIENT_EVIDENCE,
                        "Rerank confidence is below the configured evidence threshold.");
            }
            return decision(true, SelfRagDecision.RETRY_WITH_LARGER_POOL,
                    "Rerank confidence is low; retry with a larger candidate pool.");
        }

        if (singleSourceSparse(chunks, requiredChunks) && canRetry(retryCount)) {
            return decision(true, SelfRagDecision.RETRY_WITH_LARGER_POOL,
                    "Evidence is sparse and comes from a single retrieval path.");
        }

        return decision(true, SelfRagDecision.ACCEPT, "Retrieved evidence passed Self-RAG checks.");
    }

    @Override
    public QueryPlan remediate(QueryPlan queryPlan, SelfRagEvaluation evaluation) {
        QueryPlan plan = queryPlan == null ? QueryPlan.builder().build() : queryPlan;
        SelfRagDecision decision = evaluation == null ? SelfRagDecision.ACCEPT : evaluation.getDecision();

        if (decision == SelfRagDecision.RETRY_WITH_RERANK) {
            return copy(plan)
                    .mode(MODE_HYBRID_RERANK)
                    .candidatePoolSize(Math.max(plan.effectiveCandidatePoolSize(), 30))
                    .build();
        }
        if (decision == SelfRagDecision.RETRY_WITH_LARGER_POOL) {
            return copy(plan)
                    .candidatePoolSize(Math.max(plan.effectiveCandidatePoolSize() * 2, 40))
                    .topK(Math.max(plan.effectiveTopK() + 2, requiredChunks(plan)))
                    .build();
        }
        return plan;
    }

    private QueryPlan.QueryPlanBuilder copy(QueryPlan plan) {
        return QueryPlan.builder()
                .originalQuery(plan.getOriginalQuery())
                .context(plan.getContext())
                .searchQuery(plan.getSearchQuery())
                .queryType(plan.getQueryType())
                .mode(plan.effectiveMode())
                .topK(plan.effectiveTopK())
                .candidatePoolSize(plan.effectiveCandidatePoolSize())
                .vectorWeight(plan.effectiveVectorWeight())
                .bm25Weight(plan.effectiveBm25Weight());
    }

    private int requiredChunks(QueryPlan plan) {
        QueryType queryType = plan.getQueryType();
        if (queryType == QueryType.SUMMARY || queryType == QueryType.COMPARISON || queryType == QueryType.MULTI_HOP) {
            return Math.max(minFinalChunks, 3);
        }
        return minFinalChunks;
    }

    private boolean canRetry(int retryCount) {
        return retryCount < maxRetries;
    }

    private boolean rerankScoreTooLow(QueryPlan plan, List<ScoredChunk> chunks) {
        if (minRerankScore == null || !MODE_HYBRID_RERANK.equals(plan.effectiveMode())) {
            return false;
        }
        List<Double> rerankScores = chunks.stream()
                .map(ScoredChunk::getScore)
                .filter(score -> score != null && Double.isFinite(score))
                .toList();
        if (rerankScores.isEmpty()) {
            return false;
        }
        double average = rerankScores.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
        return average < minRerankScore;
    }

    private boolean singleSourceSparse(List<ScoredChunk> chunks, int requiredChunks) {
        if (chunks.size() > requiredChunks) {
            return false;
        }
        Set<String> sources = new HashSet<>();
        for (ScoredChunk chunk : chunks) {
            if (chunk.getSource() != null) {
                sources.add(chunk.getSource());
            }
        }
        return sources.size() <= 1;
    }

    private SelfRagEvaluation decision(boolean applied, SelfRagDecision decision, String reason) {
        return SelfRagEvaluation.builder()
                .applied(applied)
                .decision(decision)
                .reason(reason)
                .build();
    }
}
