package com.marrine.jchatmind.config;

import com.marrine.jchatmind.model.vo.PythonRagBridgeReadiness;
import com.marrine.jchatmind.service.impl.PythonRagMcpClient;
import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class PythonRagBridgeHealthIndicatorTest {

    @Test
    void disabledBridgeReportsUpWithoutSpawningPython() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeHealthIndicator indicator = new PythonRagBridgeHealthIndicator(properties, client);

        Health health = indicator.health();

        assertEquals(Status.UP, health.getStatus());
        assertEquals(false, health.getDetails().get("enabled"));
        assertEquals(false, health.getDetails().get("ingestionEnabled"));
        verifyNoInteractions(client);
    }

    @Test
    void enabledBridgeReportsUpWhenMcpIsReady() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        when(client.checkReadiness()).thenReturn(Optional.of(PythonRagBridgeReadiness.builder()
                .ready(true)
                .serverName("jchatmind-rag-mcp")
                .serverVersion("1.8.0")
                .tools(List.of("query_knowledge_hub", "list_collections", "get_system_status", "get_document_summary"))
                .collections(List.of("kb"))
                .collectionChunkCounts(Map.of("kb", 2))
                .totalChunks(2)
                .message("ready")
                .build()));
        PythonRagBridgeHealthIndicator indicator = new PythonRagBridgeHealthIndicator(properties, client);

        Health health = indicator.health();

        assertEquals(Status.UP, health.getStatus());
        assertEquals("jchatmind-rag-mcp", health.getDetails().get("serverName"));
        assertEquals(2, health.getDetails().get("totalChunks"));
    }

    @Test
    void enabledBridgeReportsDownWhenReadinessFails() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        when(client.checkReadiness()).thenReturn(Optional.empty());
        PythonRagBridgeHealthIndicator indicator = new PythonRagBridgeHealthIndicator(properties, client);

        Health health = indicator.health();

        assertEquals(Status.DOWN, health.getStatus());
        assertEquals("Python RAG MCP readiness check failed", health.getDetails().get("message"));
    }

    @Test
    void ingestionBridgeReportsDownWhenMcpStatusIsNotReady() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setIngestionEnabled(true);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        when(client.checkReadiness()).thenReturn(Optional.of(PythonRagBridgeReadiness.builder()
                .ready(false)
                .message("required MCP tools missing or status is not ready")
                .build()));
        PythonRagBridgeHealthIndicator indicator = new PythonRagBridgeHealthIndicator(properties, client);

        Health health = indicator.health();

        assertEquals(Status.DOWN, health.getStatus());
        assertEquals("required MCP tools missing or status is not ready", health.getDetails().get("message"));
    }
}
