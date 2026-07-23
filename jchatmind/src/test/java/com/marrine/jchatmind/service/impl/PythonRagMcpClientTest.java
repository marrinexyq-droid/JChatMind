package com.marrine.jchatmind.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.PythonRagBridgeReadiness;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PythonRagMcpClientTest {

    @Test
    void parseResponseMapsMcpCitationsToScoredChunksAndTrace() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder()
                .originalQuery("original")
                .searchQuery("hybrid retrieval")
                .mode("hybrid")
                .topK(1)
                .candidatePoolSize(20)
                .vectorWeight(1.0)
                .bm25Weight(1.0)
                .build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"citations":[{"chunk_id":"c1","document_id":"d1","text":"MCP evidence text","score":0.9,"source":"hybrid","metadata":{"title":"T"}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertEquals(1, parsed.get().getChunks().size());
        assertEquals("c1", parsed.get().getChunks().get(0).getId());
        assertEquals("MCP evidence text", parsed.get().getChunks().get(0).getContent());
        assertEquals("python-mcp:hybrid", parsed.get().getChunks().get(0).getSource());
        assertEquals("python-mcp:hybrid", parsed.get().getTrace().getMode());
        assertEquals("C1", parsed.get().getTrace().getFinalChunks().get(0).getCitationId());
        assertTrue(parsed.get().getTrace().getPartial());
        assertNull(parsed.get().getTrace().getTraceId());
        assertEquals(1, parsed.get().getTrace().getRrfResults().get(0).getRrfRank());
        assertEquals(0.9, parsed.get().getTrace().getRrfResults().get(0).getRrfScore());
    }

    @Test
    void parseResponseMapsRealPythonTraceStagesWithoutInventingRrfResults() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder()
                .originalQuery("original")
                .searchQuery("hybrid retrieval")
                .mode("hybrid-rerank")
                .topK(1)
                .candidatePoolSize(20)
                .build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-123","trace_stages":[{"name":"query_processing","method":"SearchRequest","details":{"mode":"hybrid-rerank","top_k":1}},{"name":"dense_retrieval","method":"ChromaVectorStore","details":{"results":[{"chunk_id":"dense-1","document_id":"doc-dense","score":0.91,"source":"vector","citation_id":null}]}},{"name":"sparse_retrieval","method":"SqliteSparseIndex","details":{"results":[{"chunk_id":"sparse-1","document_id":"doc-sparse","score":8.0,"source":"sparse","citation_id":null}]}},{"name":"fusion","method":"reciprocal_rank_fusion","details":{"results":[{"chunk_id":"final-1","document_id":"doc-final","score":0.77,"source":"hybrid","citation_id":null}]}},{"name":"rerank","method":"HttpReranker","details":{"fallback":true,"results":[{"chunk_id":"final-1","document_id":"doc-final","score":0.77,"source":"hybrid","citation_id":null}]}},{"name":"response_build","method":"SearchResponse","details":{"results":[{"chunk_id":"final-1","document_id":"doc-final","score":0.77,"source":"hybrid","citation_id":"C1"}]}}],"citations":[{"citation_id":"C1","chunk_id":"final-1","document_id":"doc-final","text":"MCP evidence text","score":0.77,"source":"hybrid","metadata":{"title":"T"}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertEquals("python-trace-123", parsed.get().getTrace().getTraceId());
        assertFalse(parsed.get().getTrace().getPartial());
        assertEquals("dense-1", parsed.get().getTrace().getVectorResults().get(0).getId());
        assertEquals("sparse-1", parsed.get().getTrace().getBm25Results().get(0).getId());
        assertEquals("final-1", parsed.get().getTrace().getRrfResults().get(0).getId());
        assertTrue(parsed.get().getTrace().getRerankResults().isEmpty());
        assertTrue(parsed.get().getTrace().getRerankFallback());
        assertEquals("C1", parsed.get().getTrace().getFinalChunks().get(0).getCitationId());
    }

    @Test
    void parseResponseMapsOnlyRealRerankScores() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder().searchQuery("query").mode("hybrid-rerank").topK(1).build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-rerank","trace_stages":[{"name":"query_processing","method":"SearchRequest","details":{"mode":"hybrid-rerank","top_k":1}},{"name":"rerank","method":"HttpReranker","details":{"fallback":false,"results":[{"chunk_id":"c1","document_id":"d1","score":0.96,"source":"rerank","citation_id":"C1"}]}},{"name":"response_build","method":"SearchResponse","details":{"results":[{"chunk_id":"c1","document_id":"d1","score":0.96,"source":"rerank","citation_id":"C1"}]}}],"citations":[{"citation_id":"C1","chunk_id":"c1","document_id":"d1","text":"Evidence","score":0.96,"source":"rerank","metadata":{}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertFalse(parsed.get().getTrace().getRerankFallback());
        assertEquals("c1", parsed.get().getTrace().getRerankResults().get(0).getId());
        assertEquals(1, parsed.get().getTrace().getRerankResults().get(0).getRerankRank());
        assertEquals(0.96, parsed.get().getTrace().getRerankResults().get(0).getRerankScore());
    }

    @Test
    void parseResponseDoesNotInventRerankScoresForNoopStage() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder().searchQuery("query").mode("hybrid-rerank").topK(1).build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-noop","trace_stages":[{"name":"query_processing","method":"SearchRequest","details":{"mode":"hybrid-rerank","top_k":1}},{"name":"rerank","method":"NoopReranker","details":{"fallback":false,"results":[{"chunk_id":"c1","document_id":"d1","score":0.77,"source":"hybrid","citation_id":"C1"}]}},{"name":"response_build","method":"SearchResponse","details":{"results":[{"chunk_id":"c1","document_id":"d1","score":0.77,"source":"hybrid","citation_id":"C1"}]}}],"citations":[{"citation_id":"C1","chunk_id":"c1","document_id":"d1","text":"Evidence","score":0.77,"source":"hybrid","metadata":{}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertFalse(parsed.get().getTrace().getRerankFallback());
        assertTrue(parsed.get().getTrace().getRerankResults().isEmpty());
    }

    @Test
    void parseResponseLeavesMissingRealTraceStagesEmpty() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder()
                .originalQuery("original")
                .searchQuery("dense retrieval")
                .mode("vector")
                .topK(1)
                .build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-dense","trace_stages":[{"name":"query_processing","method":"SearchRequest","details":{"mode":"vector","top_k":1}},{"name":"dense_retrieval","method":"ChromaVectorStore","details":{"results":[{"chunk_id":"dense-1","document_id":"doc-dense","score":0.91,"source":"vector","citation_id":"C1"}]}},{"name":"response_build","method":"SearchResponse","details":{"results":[{"chunk_id":"dense-1","document_id":"doc-dense","score":0.91,"source":"vector","citation_id":"C1"}]}}],"citations":[{"citation_id":"C1","chunk_id":"dense-1","document_id":"doc-dense","text":"Dense evidence","score":0.91,"source":"vector","metadata":{}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertFalse(parsed.get().getTrace().getPartial());
        assertEquals("dense-1", parsed.get().getTrace().getVectorResults().get(0).getId());
        assertTrue(parsed.get().getTrace().getBm25Results().isEmpty());
        assertTrue(parsed.get().getTrace().getRrfResults().isEmpty());
        assertTrue(parsed.get().getTrace().getRerankResults().isEmpty());
        assertEquals("C1", parsed.get().getTrace().getFinalChunks().get(0).getCitationId());
    }

    @Test
    void parseResponseMarksMalformedTracePartialAndPreservesTraceId() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder().searchQuery("query").mode("hybrid").topK(1).build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-malformed","trace_stages":[{}],"citations":[{"chunk_id":"c1","document_id":"d1","text":"Evidence","score":0.9,"source":"hybrid","metadata":{}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertTrue(parsed.get().getTrace().getPartial());
        assertEquals("python-trace-malformed", parsed.get().getTrace().getTraceId());
    }

    @Test
    void parseResponsePreservesTraceIdWhenTraceStagesAreMissing() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder().searchQuery("query").mode("hybrid").topK(1).build();
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-bridge","result":{"structuredContent":{"trace_id":"python-trace-partial","citations":[{"chunk_id":"c1","document_id":"d1","text":"Evidence","score":0.9,"source":"hybrid","metadata":{}}]}}}
                """;

        Optional<RagSearchResult> parsed = client.parseResponse(stdout, "kb", plan);

        assertTrue(parsed.isPresent());
        assertTrue(parsed.get().getTrace().getPartial());
        assertEquals("python-trace-partial", parsed.get().getTrace().getTraceId());
    }

    @Test
    void parseResponseReturnsEmptyForMcpError() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        QueryPlan plan = QueryPlan.builder().searchQuery("query").mode("hybrid").topK(1).build();

        Optional<RagSearchResult> parsed = client.parseResponse(
                "{\"jsonrpc\":\"2.0\",\"id\":\"java-rag-bridge\",\"error\":{\"message\":\"bad\"}}\n",
                "kb",
                plan
        );

        assertTrue(parsed.isEmpty());
    }

    @Test
    void parseReadinessResponseMapsInitializeToolsAndStatus() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-readiness-initialize","result":{"serverInfo":{"name":"jchatmind-rag-mcp","version":"1.8.0"}}}
                {"jsonrpc":"2.0","id":"java-rag-readiness-tools","result":{"tools":[{"name":"query_knowledge_hub"},{"name":"list_collections"},{"name":"get_system_status"},{"name":"get_document_summary"}]}}
                {"jsonrpc":"2.0","id":"java-rag-readiness-status","result":{"structuredContent":{"status":"ready","collections":["kb"],"collection_chunk_counts":{"kb":2},"total_chunks":2}}}
                """;

        Optional<PythonRagBridgeReadiness> parsed = client.parseReadinessResponse(stdout);

        assertTrue(parsed.isPresent());
        assertTrue(parsed.get().isReady());
        assertEquals("jchatmind-rag-mcp", parsed.get().getServerName());
        assertEquals("1.8.0", parsed.get().getServerVersion());
        assertEquals(4, parsed.get().getTools().size());
        assertEquals("kb", parsed.get().getCollections().get(0));
        assertEquals(2, parsed.get().getCollectionChunkCounts().get("kb"));
        assertEquals(2, parsed.get().getTotalChunks());
    }

    @Test
    void parseReadinessResponseMarksMissingRequiredToolNotReady() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());
        String stdout = """
                {"jsonrpc":"2.0","id":"java-rag-readiness-initialize","result":{"serverInfo":{"name":"jchatmind-rag-mcp","version":"1.8.0"}}}
                {"jsonrpc":"2.0","id":"java-rag-readiness-tools","result":{"tools":[{"name":"query_knowledge_hub"},{"name":"list_collections"}]}}
                {"jsonrpc":"2.0","id":"java-rag-readiness-status","result":{"structuredContent":{"status":"ready","collections":[],"collection_chunk_counts":{},"total_chunks":0}}}
                """;

        Optional<PythonRagBridgeReadiness> parsed = client.parseReadinessResponse(stdout);

        assertTrue(parsed.isPresent());
        assertFalse(parsed.get().isReady());
        assertEquals("required MCP tools missing or status is not ready", parsed.get().getMessage());
    }

    @Test
    void parseReadinessResponseReturnsEmptyForMcpError() throws Exception {
        PythonRagMcpClient client = new PythonRagMcpClient(new PythonRagBridgeProperties(), new ObjectMapper());

        Optional<PythonRagBridgeReadiness> parsed = client.parseReadinessResponse(
                "{\"jsonrpc\":\"2.0\",\"id\":\"java-rag-readiness-status\",\"error\":{\"message\":\"bad\"}}\n"
        );

        assertTrue(parsed.isEmpty());
    }
}
