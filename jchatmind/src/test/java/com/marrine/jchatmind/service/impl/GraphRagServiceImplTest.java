package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.mapper.GraphRagMapper;
import com.marrine.jchatmind.model.entity.ChunkBgeM3;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GraphRagServiceImplTest {

    @Test
    void extractsExactAndDomainEntities() {
        GraphRagServiceImpl service = new GraphRagServiceImpl(mock(GraphRagMapper.class));

        List<String> entities = service.extractEntities(
                "BB84协议与量子纠缠技术",
                "《E91协议》依赖 Bell-CHSH 模型，并通过 GraphRAG 图谱增强检索。");

        assertTrue(entities.contains("BB84"));
        assertTrue(entities.contains("E91协议"));
        assertTrue(entities.contains("Bell-CHSH"));
        assertTrue(entities.stream().anyMatch(entity -> entity.contains("图谱增强检索")));
    }

    @Test
    void expansionKeepsKbBoundaryAndConvertsChunks() {
        GraphRagMapper mapper = mock(GraphRagMapper.class);
        GraphRagServiceImpl service = new GraphRagServiceImpl(mapper);
        when(mapper.expandRelatedChunks(eq("kb-1"), anyList(), eq(2), anyInt()))
                .thenReturn(List.of(ChunkBgeM3.builder()
                        .id("chunk-2")
                        .kbId("kb-1")
                        .docId("doc-1")
                        .content("related")
                        .metadata("{}")
                        .build()));

        List<ScoredChunk> expanded = service.expandRelatedChunks("kb-1", List.of(seed("chunk-1")), 2, 5);

        assertEquals(1, expanded.size());
        assertEquals("kb-1", expanded.get(0).getKbId());
        assertEquals("graph", expanded.get(0).getSource());
        verify(mapper).expandRelatedChunks(eq("kb-1"), anyList(), eq(2), eq(5));
    }

    private ScoredChunk seed(String id) {
        return ScoredChunk.builder()
                .id(id)
                .kbId("kb-1")
                .docId("doc-1")
                .content("seed")
                .source("hybrid")
                .score(1.0)
                .build();
    }
}
