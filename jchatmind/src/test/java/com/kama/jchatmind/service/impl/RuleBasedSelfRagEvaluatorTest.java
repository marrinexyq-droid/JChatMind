package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.QueryType;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.model.vo.SelfRagDecision;
import com.kama.jchatmind.model.vo.SelfRagEvaluation;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class RuleBasedSelfRagEvaluatorTest {

    @Test
    void emptyResultsAreInsufficientEvidence() {
        RuleBasedSelfRagEvaluator evaluator = evaluator();
        SelfRagEvaluation evaluation = evaluator.evaluate(factPlan("hybrid"), result(List.of()), 0);

        assertEquals(SelfRagDecision.INSUFFICIENT_EVIDENCE, evaluation.getDecision());
    }

    @Test
    void weakNonRerankResultsRetryWithRerank() {
        RuleBasedSelfRagEvaluator evaluator = evaluator();
        SelfRagEvaluation evaluation = evaluator.evaluate(factPlan("hybrid"), result(List.of(chunk("c1", "hybrid", 1.0))), 0);

        assertEquals(SelfRagDecision.RETRY_WITH_RERANK, evaluation.getDecision());
    }

    @Test
    void sparseSummaryResultsRetryWithLargerPoolAfterRerank() {
        RuleBasedSelfRagEvaluator evaluator = evaluator();
        QueryPlan plan = QueryPlan.builder()
                .originalQuery("summary")
                .searchQuery("summary")
                .queryType(QueryType.SUMMARY)
                .mode("hybrid-rerank")
                .topK(10)
                .candidatePoolSize(40)
                .build();

        SelfRagEvaluation evaluation = evaluator.evaluate(plan, result(List.of(
                chunk("c1", "rerank", 1.0),
                chunk("c2", "rerank", 0.9)
        )), 0);

        assertEquals(SelfRagDecision.RETRY_WITH_LARGER_POOL, evaluation.getDecision());
    }

    @Test
    void sufficientResultsAreAccepted() {
        RuleBasedSelfRagEvaluator evaluator = evaluator();
        SelfRagEvaluation evaluation = evaluator.evaluate(factPlan("hybrid-rerank"), result(List.of(
                chunk("c1", "rerank", 1.0),
                chunk("c2", "rerank", 0.9),
                chunk("c3", "rerank", 0.8)
        )), 0);

        assertEquals(SelfRagDecision.ACCEPT, evaluation.getDecision());
    }

    private RuleBasedSelfRagEvaluator evaluator() {
        return new RuleBasedSelfRagEvaluator(true, 2, null, 1);
    }

    private QueryPlan factPlan(String mode) {
        return QueryPlan.builder()
                .originalQuery("fact")
                .searchQuery("fact")
                .queryType(QueryType.FACT)
                .mode(mode)
                .topK(5)
                .candidatePoolSize(20)
                .build();
    }

    private RagSearchResult result(List<ScoredChunk> chunks) {
        return RagSearchResult.builder().chunks(chunks).build();
    }

    private ScoredChunk chunk(String id, String source, double score) {
        return ScoredChunk.builder()
                .id(id)
                .kbId("kb")
                .docId("doc")
                .content("content")
                .source(source)
                .score(score)
                .build();
    }
}
