package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.RerankRequest;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.service.RerankService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.util.*;

/**
 * Cross-Encoder Reranking 实现，调用本地 Python FastAPI 服务 (sentence-transformers)
 */
@Service
@Slf4j
public class RerankServiceImpl implements RerankService {

    private final RestClient restClient;

    public RerankServiceImpl(
            RestClient.Builder builder,
            @Value("${reranker.base-url:http://127.0.0.1:8001}") String baseUrl) {
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.restClient = builder.baseUrl(baseUrl)
                .requestFactory(new JdkClientHttpRequestFactory(httpClient))
                .build();
    }

    @Override
    public List<ScoredChunk> rerank(String query, List<ScoredChunk> candidates, int topK) {
        if (candidates == null || candidates.isEmpty()) {
            return Collections.emptyList();
        }

        try {
            long start = System.currentTimeMillis();

            List<String> texts = candidates.stream()
                    .map(c -> c.getContent() != null ? c.getContent() : "")
                    .toList();

            String safeQuery = query != null ? query : "";
            RerankRequest body = new RerankRequest(safeQuery, texts);

            log.info("Rerank request: queryLen={}, docsCount={}",
                    safeQuery.length(), texts.size());

            List<Map<String, Object>> rawScores = restClient.post()
                    .uri("/rerank")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(s -> s.isError(), (req, resp) -> {
                        String errBody = new String(resp.getBody().readAllBytes());
                        throw new RuntimeException(resp.getStatusCode() + " " + errBody);
                    })
                    .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {});

            if (rawScores == null || rawScores.isEmpty()) {
                log.warn("Rerank 返回空结果，使用原始顺序");
                return candidates.stream().limit(topK).toList();
            }

            List<ScoredChunk> result = new ArrayList<>();
            for (Object item : rawScores) {
                if (!(item instanceof Map)) continue;
                Map<?, ?> map = (Map<?, ?>) item;
                Object scoreObj = map.get("score");
                Object indexObj = map.get("index");
                if (scoreObj == null || indexObj == null) continue;
                float score = ((Number) scoreObj).floatValue();
                int idx = ((Number) indexObj).intValue();
                if (idx >= 0 && idx < candidates.size()) {
                    ScoredChunk original = candidates.get(idx);
                    result.add(ScoredChunk.builder()
                            .id(original.getId())
                            .kbId(original.getKbId())
                            .docId(original.getDocId())
                            .content(original.getContent())
                            .metadata(original.getMetadata())
                            .source("rerank")
                            .score(score)
                            .build());
                }
            }

            result.sort((a, b) -> Double.compare(b.getScore(), a.getScore()));
            List<ScoredChunk> topResults = result.stream().limit(topK).toList();

            long elapsed = System.currentTimeMillis() - start;
            log.info("Rerank 完成: candidates={}, topK={}, elapsed={}ms",
                    candidates.size(), topK, elapsed);

            return topResults;

        } catch (Exception e) {
            log.error("Rerank 调用失败，回退到原始排序: {}", e.getMessage());
            return candidates.stream().limit(topK).toList();
        }
    }
}
