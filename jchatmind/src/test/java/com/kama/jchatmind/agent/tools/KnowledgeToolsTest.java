package com.kama.jchatmind.agent.tools;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.RagTrace;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.model.vo.SelfRagDecision;
import com.kama.jchatmind.model.vo.SelfRagEvaluation;
import com.kama.jchatmind.service.QueryPlanner;
import com.kama.jchatmind.service.RagService;
import com.kama.jchatmind.service.SelfRagEvaluator;
import org.junit.jupiter.api.Test;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class KnowledgeToolsTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void contextParameterIsOptionalInToolSchema() throws Exception {
        ToolCallback callback = MethodToolCallbackProvider.builder()
                .toolObjects(new KnowledgeTools(null, null))
                .build()
                .getToolCallbacks()[0];

        JsonNode schema = objectMapper.readTree(callback.getToolDefinition().inputSchema());
        JsonNode properties = schema.path("properties");
        List<String> required = new ArrayList<>();
        schema.path("required").forEach(node -> required.add(node.asText()));

        assertTrue(properties.has("kbsId"));
        assertTrue(properties.has("query"));
        assertTrue(properties.has("context"));
        assertTrue(required.contains("kbsId"));
        assertTrue(required.contains("query"));
        assertFalse(required.contains("context"));
    }

    @Test
    void acceptedEvidenceSearchesOnce() {
        QueryPlan plan = plan("hybrid");
        RagService ragService = mock(RagService.class);
        QueryPlanner queryPlanner = mock(QueryPlanner.class);
        SelfRagEvaluator selfRagEvaluator = mock(SelfRagEvaluator.class);
        when(queryPlanner.plan("query", null)).thenReturn(plan);
        when(ragService.hybridSearchWithTrace("kb", plan)).thenReturn(result("trace-1", chunk("c1"), chunk("c2")));
        when(selfRagEvaluator.evaluate(eq(plan), any(RagSearchResult.class), eq(0))).thenReturn(accept());

        String response = new KnowledgeTools(ragService, queryPlanner, selfRagEvaluator)
                .knowledgeQuery("kb", "query", null);

        assertTrue(response.contains("[C1]"));
        verify(ragService, times(1)).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    @Test
    void retryDecisionSearchesAtMostTwice() {
        QueryPlan firstPlan = plan("hybrid");
        QueryPlan retryPlan = plan("hybrid-rerank");
        RagService ragService = mock(RagService.class);
        QueryPlanner queryPlanner = mock(QueryPlanner.class);
        SelfRagEvaluator selfRagEvaluator = mock(SelfRagEvaluator.class);
        when(queryPlanner.plan("query", null)).thenReturn(firstPlan);
        when(ragService.hybridSearchWithTrace("kb", firstPlan)).thenReturn(result("trace-1", chunk("c1")));
        when(ragService.hybridSearchWithTrace("kb", retryPlan)).thenReturn(result("trace-2", chunk("c1"), chunk("c2")));
        when(selfRagEvaluator.evaluate(eq(firstPlan), any(RagSearchResult.class), eq(0))).thenReturn(retryWithRerank());
        when(selfRagEvaluator.remediate(firstPlan, retryWithRerank())).thenReturn(retryPlan);
        when(selfRagEvaluator.evaluate(eq(retryPlan), any(RagSearchResult.class), eq(1))).thenReturn(accept());

        String response = new KnowledgeTools(ragService, queryPlanner, selfRagEvaluator)
                .knowledgeQuery("kb", "query", null);

        assertTrue(response.contains("[C2]"));
        verify(ragService, times(2)).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    @Test
    void retryFailureReturnsInsufficientEvidence() {
        QueryPlan firstPlan = plan("hybrid");
        QueryPlan retryPlan = plan("hybrid-rerank");
        RagService ragService = mock(RagService.class);
        QueryPlanner queryPlanner = mock(QueryPlanner.class);
        SelfRagEvaluator selfRagEvaluator = mock(SelfRagEvaluator.class);
        when(queryPlanner.plan("query", null)).thenReturn(firstPlan);
        when(ragService.hybridSearchWithTrace("kb", firstPlan)).thenReturn(result("trace-1", chunk("c1")));
        when(ragService.hybridSearchWithTrace("kb", retryPlan)).thenReturn(result("trace-2", chunk("c1")));
        when(selfRagEvaluator.evaluate(eq(firstPlan), any(RagSearchResult.class), eq(0))).thenReturn(retryWithRerank());
        when(selfRagEvaluator.remediate(firstPlan, retryWithRerank())).thenReturn(retryPlan);
        when(selfRagEvaluator.evaluate(eq(retryPlan), any(RagSearchResult.class), eq(1))).thenReturn(insufficient());

        String response = new KnowledgeTools(ragService, queryPlanner, selfRagEvaluator)
                .knowledgeQuery("kb", "query", null);

        assertTrue(response.contains("insufficient"));
        verify(ragService, times(2)).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    private QueryPlan plan(String mode) {
        return QueryPlan.builder()
                .originalQuery("query")
                .searchQuery("query")
                .mode(mode)
                .topK(5)
                .candidatePoolSize(20)
                .build();
    }

    private RagSearchResult result(String query, ScoredChunk... chunks) {
        return RagSearchResult.builder()
                .chunks(List.of(chunks))
                .trace(RagTrace.builder().query(query).build())
                .build();
    }

    private ScoredChunk chunk(String id) {
        return ScoredChunk.builder()
                .id(id)
                .kbId("kb")
                .docId("doc")
                .content("content " + id)
                .source("hybrid")
                .score(1.0)
                .build();
    }

    private SelfRagEvaluation accept() {
        return SelfRagEvaluation.builder()
                .applied(true)
                .decision(SelfRagDecision.ACCEPT)
                .reason("ok")
                .build();
    }

    private SelfRagEvaluation retryWithRerank() {
        return SelfRagEvaluation.builder()
                .applied(true)
                .decision(SelfRagDecision.RETRY_WITH_RERANK)
                .reason("retry")
                .build();
    }

    private SelfRagEvaluation insufficient() {
        return SelfRagEvaluation.builder()
                .applied(true)
                .decision(SelfRagDecision.INSUFFICIENT_EVIDENCE)
                .reason("not enough")
                .build();
    }
}
