package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.ScoredChunk;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

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
}
