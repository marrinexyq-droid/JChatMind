package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.PythonRagBridgeReadiness;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PythonBridgeRagServiceTest {

    @Test
    void disabledBridgeDelegatesToLegacyRag() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        QueryPlan plan = plan();
        RagSearchResult legacyResult = result("legacy");
        when(legacy.hybridSearchWithTrace("kb", plan)).thenReturn(legacyResult);

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(legacyResult, service.hybridSearchWithTrace("kb", plan));
        verify(client, never()).search(any(), any());
    }

    @Test
    void enabledBridgeReturnsPythonResultWhenChunksExist() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        QueryPlan plan = plan();
        RagSearchResult pythonResult = result("python");
        when(client.search("kb", plan)).thenReturn(Optional.of(pythonResult));

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(pythonResult, service.hybridSearchWithTrace("kb", plan));
        verify(legacy, never()).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    @Test
    void readinessGateAllowsPythonSearchWhenReady() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = enabledWithReadinessGate();
        QueryPlan plan = plan();
        RagSearchResult pythonResult = result("python");
        when(client.checkReadiness()).thenReturn(Optional.of(readiness(true)));
        when(client.search("kb", plan)).thenReturn(Optional.of(pythonResult));

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(pythonResult, service.hybridSearchWithTrace("kb", plan));
        verify(client).checkReadiness();
        verify(client).search("kb", plan);
        verify(legacy, never()).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    @Test
    void readinessGateFallsBackWhenReadinessFails() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = enabledWithReadinessGate();
        QueryPlan plan = plan();
        RagSearchResult legacyResult = result("legacy");
        when(client.checkReadiness()).thenReturn(Optional.empty());
        when(legacy.hybridSearchWithTrace("kb", plan)).thenReturn(legacyResult);

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(legacyResult, service.hybridSearchWithTrace("kb", plan));
        verify(client, never()).search(any(), any());
    }

    @Test
    void readinessGateReturnsEmptyWhenFailClosedAndNotReady() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = enabledWithReadinessGate();
        properties.setFallbackOnError(false);
        QueryPlan plan = plan();
        when(client.checkReadiness()).thenReturn(Optional.of(readiness(false)));

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(List.of(), service.hybridSearchWithTrace("kb", plan).getChunks());
        verify(client, never()).search(any(), any());
        verify(legacy, never()).hybridSearchWithTrace(eq("kb"), any(QueryPlan.class));
    }

    @Test
    void readinessGateCachesReadinessWithinTtl() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = enabledWithReadinessGate();
        properties.setReadinessCacheTtlMs(60000);
        QueryPlan plan = plan();
        when(client.checkReadiness()).thenReturn(Optional.of(readiness(true)));
        when(client.search("kb", plan)).thenReturn(Optional.of(result("python-1")), Optional.of(result("python-2")));

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals("python-1", service.hybridSearchWithTrace("kb", plan).getChunks().get(0).getId());
        assertEquals("python-2", service.hybridSearchWithTrace("kb", plan).getChunks().get(0).getId());
        verify(client, times(1)).checkReadiness();
        verify(client, times(2)).search("kb", plan);
    }

    @Test
    void enabledBridgeFallsBackToLegacyWhenPythonFails() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        QueryPlan plan = plan();
        RagSearchResult legacyResult = result("legacy");
        when(client.search("kb", plan)).thenReturn(Optional.empty());
        when(legacy.hybridSearchWithTrace("kb", plan)).thenReturn(legacyResult);

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(legacyResult, service.hybridSearchWithTrace("kb", plan));
    }

    @Test
    void fallbackOnEmptyIsIndependentFromFallbackOnError() {
        RagServiceImpl legacy = mock(RagServiceImpl.class);
        PythonRagMcpClient client = mock(PythonRagMcpClient.class);
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        properties.setFallbackOnError(false);
        properties.setFallbackOnEmpty(true);
        QueryPlan plan = plan();
        RagSearchResult legacyResult = result("legacy");
        when(client.search("kb", plan)).thenReturn(Optional.of(RagSearchResult.builder().chunks(List.of()).build()));
        when(legacy.hybridSearchWithTrace("kb", plan)).thenReturn(legacyResult);

        PythonBridgeRagService service = new PythonBridgeRagService(legacy, client, properties);

        assertEquals(legacyResult, service.hybridSearchWithTrace("kb", plan));
    }

    private QueryPlan plan() {
        return QueryPlan.builder()
                .originalQuery("query")
                .searchQuery("query")
                .mode("hybrid")
                .topK(3)
                .candidatePoolSize(20)
                .build();
    }

    private RagSearchResult result(String id) {
        return RagSearchResult.builder()
                .chunks(List.of(ScoredChunk.builder()
                        .id(id)
                        .kbId("kb")
                        .docId("doc")
                        .content("content")
                        .source("hybrid")
                        .score(1.0)
                        .build()))
                .build();
    }

    private PythonRagBridgeProperties enabledWithReadinessGate() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setEnabled(true);
        properties.setReadinessGateEnabled(true);
        properties.setReadinessCacheTtlMs(15000);
        return properties;
    }

    private PythonRagBridgeReadiness readiness(boolean ready) {
        return PythonRagBridgeReadiness.builder()
                .ready(ready)
                .message(ready ? "ready" : "not ready")
                .build();
    }
}
