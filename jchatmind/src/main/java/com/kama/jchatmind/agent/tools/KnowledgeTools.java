package com.kama.jchatmind.agent.tools;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.model.vo.SelfRagDecision;
import com.kama.jchatmind.model.vo.SelfRagEvaluation;
import com.kama.jchatmind.service.QueryPlanner;
import com.kama.jchatmind.service.RagService;
import com.kama.jchatmind.service.RagTraceContext;
import com.kama.jchatmind.service.SelfRagEvaluator;
import org.springframework.stereotype.Component;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.util.StringUtils;

import java.util.List;

@Component
public class KnowledgeTools implements Tool {
    private static final int SELF_RAG_TOOL_RETRY_LIMIT = 1;

    private final RagService ragService;
    private final QueryPlanner queryPlanner;
    private final SelfRagEvaluator selfRagEvaluator;

    public KnowledgeTools(RagService ragService, QueryPlanner queryPlanner, SelfRagEvaluator selfRagEvaluator) {
        this.ragService = ragService;
        this.queryPlanner = queryPlanner;
        this.selfRagEvaluator = selfRagEvaluator;
    }

    KnowledgeTools(RagService ragService, QueryPlanner queryPlanner) {
        this(ragService, queryPlanner, null);
    }

    @Override
    public String getName() {
        return "KnowledgeTool";
    }

    @Override
    public String getDescription() {
        return "Search the knowledge base with hybrid retrieval by default; rerank is optional for high-quality mode.";
    }

    @Override
    public ToolType getType() {
        return ToolType.FIXED;
    }

    @org.springframework.ai.tool.annotation.Tool(
            name = "KnowledgeTool",
            description = "Search a specified knowledge base. Parameters are kbsId, query, and optional context for follow-up questions. Returns retrieved chunks marked as [C1], [C2], etc.; cite those markers in the final answer."
    )
    public String knowledgeQuery(
            @ToolParam(description = "Knowledge base ID to search") String kbsId,
            @ToolParam(description = "User question or search query") String query,
            @ToolParam(required = false, description = "Previous topic for follow-up questions") String context) {
        if (!StringUtils.hasLength(kbsId) || !StringUtils.hasLength(query)) {
            return "Invalid parameters: kbsId and query cannot be empty.";
        }

        QueryPlan queryPlan = queryPlanner.plan(query, context);
        int retryCount = 0;
        RagSearchResult searchResult = ragService.hybridSearchWithTrace(kbsId, queryPlan);
        SelfRagEvaluation evaluation = evaluate(queryPlan, searchResult, retryCount);

        while (isRetry(evaluation) && retryCount < SELF_RAG_TOOL_RETRY_LIMIT) {
            retryCount++;
            queryPlan = selfRagEvaluator.remediate(queryPlan, evaluation);
            searchResult = ragService.hybridSearchWithTrace(kbsId, queryPlan);
            evaluation = evaluate(queryPlan, searchResult, retryCount);
        }
        if (isRetry(evaluation)) {
            evaluation = SelfRagEvaluation.builder()
                    .applied(evaluation.isApplied())
                    .decision(SelfRagDecision.INSUFFICIENT_EVIDENCE)
                    .reason("Self-RAG retry limit reached before evidence passed quality checks.")
                    .build();
        }

        applySelfRagTrace(searchResult, evaluation, retryCount);
        RagTraceContext.set(searchResult.getTrace());
        List<ScoredChunk> results = searchResult.getChunks();

        if (evaluation.getDecision() == SelfRagDecision.INSUFFICIENT_EVIDENCE) {
            return "Knowledge base evidence is insufficient for a reliable answer. " + evaluation.getReason();
        }

        if (results == null || results.isEmpty()) {
            return "No relevant content found.";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("Use the following retrieved chunks as evidence. ")
                .append("When answering with information from a chunk, cite the matching marker like [C1].\n\n");

        for (int i = 0; i < results.size(); i++) {
            ScoredChunk chunk = results.get(i);
            sb.append(String.format("[C%d] (source: %s, score: %.4f, docId: %s)%n%s%n",
                    i + 1,
                    chunk.getSource(),
                    chunk.getScore(),
                    chunk.getDocId(),
                    chunk.getContent()));
            if (i < results.size() - 1) {
                sb.append("\n---\n\n");
            }
        }
        return sb.toString();
    }

    public String knowledgeQuery(String kbsId, String query) {
        return knowledgeQuery(kbsId, query, null);
    }

    private SelfRagEvaluation evaluate(QueryPlan queryPlan, RagSearchResult searchResult, int retryCount) {
        if (selfRagEvaluator == null) {
            return SelfRagEvaluation.builder()
                    .applied(false)
                    .decision(SelfRagDecision.ACCEPT)
                    .reason("Self-RAG evaluator is not configured.")
                    .build();
        }
        return selfRagEvaluator.evaluate(queryPlan, searchResult, retryCount);
    }

    private boolean isRetry(SelfRagEvaluation evaluation) {
        if (selfRagEvaluator == null || evaluation == null) {
            return false;
        }
        return evaluation.getDecision() == SelfRagDecision.RETRY_WITH_RERANK
                || evaluation.getDecision() == SelfRagDecision.RETRY_WITH_LARGER_POOL;
    }

    private void applySelfRagTrace(RagSearchResult searchResult, SelfRagEvaluation evaluation, int retryCount) {
        if (searchResult == null || searchResult.getTrace() == null || evaluation == null) {
            return;
        }
        searchResult.getTrace().setSelfRagApplied(evaluation.isApplied());
        searchResult.getTrace().setSelfRagDecision(evaluation.getDecision().name());
        searchResult.getTrace().setSelfRagReason(evaluation.getReason());
        searchResult.getTrace().setSelfRagRetryCount(retryCount);
    }
}
