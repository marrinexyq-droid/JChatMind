package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.mapper.ChunkBgeM3Mapper;
import com.marrine.jchatmind.mapper.DocumentMapper;
import com.marrine.jchatmind.model.entity.ChunkBgeM3;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import com.marrine.jchatmind.service.GraphRagService;
import com.marrine.jchatmind.service.RerankService;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RagServiceImplTest {

    private final RagServiceImpl ragService = new RagServiceImpl(WebClient.builder(), null, null, null);

    @Test
    void rrfDefaultWeightsPreserveBalancedHybridPreference() {
        ScoredChunk vectorOnly = chunk("vector-only", "vector");
        ScoredChunk shared = chunk("shared", "vector");
        ScoredChunk bm25Only = chunk("bm25-only", "bm25");

        List<ScoredChunk> fused = ragService.reciprocalRankFusion(
                List.of(vectorOnly, shared),
                List.of(shared, bm25Only),
                1.0,
                1.0
        );

        assertEquals("shared", fused.get(0).getId());
    }

    @Test
    void rrfBm25WeightCanPromoteBm25Result() {
        ScoredChunk vectorTop = chunk("vector-top", "vector");
        ScoredChunk bm25Top = chunk("bm25-top", "bm25");

        List<ScoredChunk> fused = ragService.reciprocalRankFusion(
                List.of(vectorTop),
                List.of(bm25Top),
                1.0,
                2.0
        );

        assertEquals("bm25-top", fused.get(0).getId());
    }

    @Test
    void nullModeFallsBackToHybridWithoutRerank() throws IOException {
        HttpServer server = embeddingServer();
        try {
            ChunkBgeM3Mapper chunkMapper = mock(ChunkBgeM3Mapper.class);
            DocumentMapper documentMapper = mock(DocumentMapper.class);
            RerankService rerankService = mock(RerankService.class);
            RagServiceImpl service = service(server, chunkMapper, documentMapper, rerankService);
            stubRetrieval(chunkMapper);

            RagSearchResult result = service.hybridSearchWithTrace("kb", "query", 2, null);

            assertEquals("hybrid", result.getTrace().getMode());
            assertFalse(result.getTrace().getRerankApplied());
            verify(rerankService, never()).rerank(anyString(), anyList(), anyInt());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void unknownModeFallsBackToHybridWithoutRerank() throws IOException {
        HttpServer server = embeddingServer();
        try {
            ChunkBgeM3Mapper chunkMapper = mock(ChunkBgeM3Mapper.class);
            DocumentMapper documentMapper = mock(DocumentMapper.class);
            RerankService rerankService = mock(RerankService.class);
            RagServiceImpl service = service(server, chunkMapper, documentMapper, rerankService);
            stubRetrieval(chunkMapper);

            RagSearchResult result = service.hybridSearchWithTrace("kb", "query", 2, "unexpected");

            assertEquals("hybrid", result.getTrace().getMode());
            assertFalse(result.getTrace().getRerankApplied());
            verify(rerankService, never()).rerank(anyString(), anyList(), anyInt());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void hybridRerankModeCallsRerankAndMarksFallbackWhenRerankReturnsFusedOrder() throws IOException {
        HttpServer server = embeddingServer();
        try {
            ChunkBgeM3Mapper chunkMapper = mock(ChunkBgeM3Mapper.class);
            DocumentMapper documentMapper = mock(DocumentMapper.class);
            RerankService rerankService = mock(RerankService.class);
            RagServiceImpl service = service(server, chunkMapper, documentMapper, rerankService);
            stubRetrieval(chunkMapper);
            when(rerankService.rerank(anyString(), anyList(), anyInt()))
                    .thenAnswer(invocation -> invocation.getArgument(1, List.class));

            RagSearchResult result = service.hybridSearchWithTrace("kb", "query", 2, "hybrid-rerank");

            assertEquals("hybrid-rerank", result.getTrace().getMode());
            assertTrue(result.getTrace().getRerankApplied());
            assertTrue(result.getTrace().getRerankFallback());
            verify(rerankService).rerank(anyString(), anyList(), anyInt());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void graphExpansionIsTracedAndPassedIntoRerank() throws IOException {
        HttpServer server = embeddingServer();
        try {
            ChunkBgeM3Mapper chunkMapper = mock(ChunkBgeM3Mapper.class);
            DocumentMapper documentMapper = mock(DocumentMapper.class);
            RerankService rerankService = mock(RerankService.class);
            GraphRagService graphRagService = mock(GraphRagService.class);
            RagServiceImpl service = new RagServiceImpl(WebClient.builder(), chunkMapper, documentMapper, rerankService,
                    "http://localhost:" + server.getAddress().getPort(), graphRagService);
            stubRetrieval(chunkMapper);
            when(graphRagService.expandRelatedChunks(anyString(), anyList(), anyInt(), anyInt()))
                    .thenReturn(List.of(chunk("graph-only", "graph")));
            when(rerankService.rerank(anyString(), anyList(), anyInt()))
                    .thenAnswer(invocation -> invocation.getArgument(1, List.class));

            QueryPlan plan = QueryPlan.builder()
                    .originalQuery("query")
                    .searchQuery("query")
                    .mode("hybrid-rerank")
                    .topK(4)
                    .candidatePoolSize(20)
                    .vectorWeight(1.0)
                    .bm25Weight(1.0)
                    .graphExpansionEnabled(true)
                    .graphMaxHops(2)
                    .build();
            RagSearchResult result = service.hybridSearchWithTrace("kb", plan);

            assertTrue(result.getTrace().getGraphExpansionEnabled());
            assertEquals(2, result.getTrace().getGraphMaxHops());
            assertEquals(1, result.getTrace().getGraphExpandedChunks().size());
            assertTrue(result.getChunks().stream().anyMatch(chunk -> "graph-only".equals(chunk.getId())));
            verify(graphRagService).expandRelatedChunks(anyString(), anyList(), anyInt(), anyInt());
        } finally {
            server.stop(0);
        }
    }

    private ScoredChunk chunk(String id, String source) {
        return ScoredChunk.builder()
                .id(id)
                .kbId("kb")
                .docId("doc")
                .content("content")
                .source(source)
                .score(1.0)
                .build();
    }

    private RagServiceImpl service(HttpServer server,
                                   ChunkBgeM3Mapper chunkMapper,
                                   DocumentMapper documentMapper,
                                   RerankService rerankService) {
        return new RagServiceImpl(WebClient.builder(), chunkMapper, documentMapper, rerankService,
                "http://localhost:" + server.getAddress().getPort());
    }

    private void stubRetrieval(ChunkBgeM3Mapper chunkMapper) {
        when(chunkMapper.similaritySearch(anyString(), anyString(), anyInt()))
                .thenReturn(List.of(entityChunk("vector-shared", "doc-1"), entityChunk("vector-only", "doc-2")));
        when(chunkMapper.bm25Search(anyString(), anyString(), anyInt()))
                .thenReturn(List.of(entityChunk("vector-shared", "doc-1"), entityChunk("bm25-only", "doc-3")));
    }

    private ChunkBgeM3 entityChunk(String id, String docId) {
        return ChunkBgeM3.builder()
                .id(id)
                .kbId("kb")
                .docId(docId)
                .content("content " + id)
                .metadata("{}")
                .build();
    }

    private HttpServer embeddingServer() throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/api/embeddings", exchange -> {
            byte[] body = "{\"embedding\":[0.1,0.2,0.3]}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        return server;
    }
}
