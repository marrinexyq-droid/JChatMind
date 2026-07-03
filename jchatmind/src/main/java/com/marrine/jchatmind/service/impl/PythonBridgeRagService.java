package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import com.marrine.jchatmind.service.RagService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
@Primary
@Slf4j
@RequiredArgsConstructor
public class PythonBridgeRagService implements RagService {
    private final RagServiceImpl legacyRagService;
    private final PythonRagMcpClient pythonRagMcpClient;
    private final PythonRagBridgeProperties properties;

    @Override
    public float[] embed(String text) {
        return legacyRagService.embed(text);
    }

    @Override
    public List<String> similaritySearch(String kbId, String title) {
        return legacyRagService.similaritySearch(kbId, title);
    }

    @Override
    public List<ScoredChunk> hybridSearch(String kbId, String query, int topK, String mode) {
        return hybridSearchWithTrace(kbId, query, topK, mode).getChunks();
    }

    @Override
    public RagSearchResult hybridSearchWithTrace(String kbId, String query, int topK, String mode) {
        QueryPlan queryPlan = QueryPlan.builder()
                .originalQuery(query)
                .searchQuery(query)
                .mode(mode)
                .topK(topK)
                .candidatePoolSize(20)
                .vectorWeight(1.0)
                .bm25Weight(1.0)
                .build();
        return hybridSearchWithTrace(kbId, queryPlan);
    }

    @Override
    public RagSearchResult hybridSearchWithTrace(String kbId, QueryPlan queryPlan) {
        if (!properties.isEnabled()) {
            return legacyRagService.hybridSearchWithTrace(kbId, queryPlan);
        }

        Optional<RagSearchResult> pythonResult = pythonRagMcpClient.search(kbId, queryPlan);
        if (pythonResult.isPresent()) {
            RagSearchResult result = pythonResult.get();
            if (!properties.isFallbackOnEmpty() || (result.getChunks() != null && !result.getChunks().isEmpty())) {
                return result;
            }
            log.warn("Python RAG MCP returned no chunks; falling back to Java RAG for kbId={}", kbId);
            return legacyRagService.hybridSearchWithTrace(kbId, queryPlan);
        } else {
            log.warn("Python RAG MCP returned no result for kbId={}", kbId);
        }

        if (properties.isFallbackOnError()) {
            return legacyRagService.hybridSearchWithTrace(kbId, queryPlan);
        }
        return pythonResult.orElseGet(() -> RagSearchResult.builder().chunks(List.of()).build());
    }

    @Override
    public void ensureIndexes() {
        legacyRagService.ensureIndexes();
    }
}
