package com.marrine.jchatmind.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
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
}
