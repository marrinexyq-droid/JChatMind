package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.mapper.ChunkBgeM3Mapper;
import com.kama.jchatmind.model.entity.ChunkBgeM3;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.service.RagService;
import com.kama.jchatmind.service.RerankService;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.Assert;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;

@Service
@Slf4j
public class RagServiceImpl implements RagService {

    private static final int RRF_K = 60;
    private static final int CANDIDATE_POOL_SIZE = 20;

    // 专用线程池用于并行检索（阻塞 JDBC/HTTP 调用不应使用 ForkJoinPool commonPool）
    private final ExecutorService searchExecutor = Executors.newFixedThreadPool(4);

    private final WebClient webClient;
    private final ChunkBgeM3Mapper chunkBgeM3Mapper;
    private final RerankService rerankService;

    public RagServiceImpl(WebClient.Builder builder,
                          ChunkBgeM3Mapper chunkBgeM3Mapper,
                          RerankService rerankService) {
        this.webClient = builder.baseUrl("http://localhost:11434").build();
        this.chunkBgeM3Mapper = chunkBgeM3Mapper;
        this.rerankService = rerankService;
    }

    @Data
    private static class EmbeddingResponse {
        private float[] embedding;
    }

    private float[] doEmbed(String text) {
        EmbeddingResponse resp = webClient.post()
                .uri("/api/embeddings")
                .bodyValue(Map.of(
                        "model", "bge-m3",
                        "prompt", text
                ))
                .retrieve()
                .bodyToMono(EmbeddingResponse.class)
                .block();
        Assert.notNull(resp, "Embedding response cannot be null");
        return resp.getEmbedding();
    }

    @Override
    public float[] embed(String text) {
        return doEmbed(text);
    }

    // ==================== 纯向量检索（保留兼容） ====================

    @Override
    public List<String> similaritySearch(String kbId, String title) {
        String queryEmbedding = toPgVector(doEmbed(title));
        List<ChunkBgeM3> chunks = chunkBgeM3Mapper.similaritySearch(kbId, queryEmbedding, 3);
        return chunks.stream().map(ChunkBgeM3::getContent).toList();
    }

    // ==================== 混合检索 ====================

    @Override
    public List<ScoredChunk> hybridSearch(String kbId, String query, int topK, String mode) {
        long start = System.currentTimeMillis();

        // "vector" 模式：只跑向量检索
        if ("vector".equals(mode)) {
            List<ScoredChunk> vectorResults = vectorSearch(kbId, query, topK);
            log.info("Vector-only search: topK={}, elapsed={}ms", topK, System.currentTimeMillis() - start);
            return vectorResults;
        }

        // "hybrid" / "hybrid-rerank" 模式：并行执行向量 + BM25（使用专用线程池避免阻塞 commonPool）
        CompletableFuture<List<ScoredChunk>> vectorFuture = CompletableFuture.supplyAsync(
                () -> vectorSearch(kbId, query, CANDIDATE_POOL_SIZE), searchExecutor);
        CompletableFuture<List<ScoredChunk>> bm25Future = CompletableFuture.supplyAsync(
                () -> bm25Search(kbId, query, CANDIDATE_POOL_SIZE), searchExecutor);

        CompletableFuture.allOf(vectorFuture, bm25Future).join();

        List<ScoredChunk> vectorResults = vectorFuture.join();
        List<ScoredChunk> bm25Results = bm25Future.join();
        List<ScoredChunk> fused = reciprocalRankFusion(vectorResults, bm25Results);

        log.info("Hybrid search: vector={}, bm25={}, fused={}",
                vectorResults.size(), bm25Results.size(), fused.size());

        if (fused.isEmpty()) {
            return Collections.emptyList();
        }

        // "hybrid" 模式跳过 rerank
        if ("hybrid".equals(mode)) {
            List<ScoredChunk> topResults = fused.stream().limit(topK).toList();
            log.info("Hybrid search (no rerank) 完成: topK={}, elapsed={}ms", topK, System.currentTimeMillis() - start);
            return topResults;
        }

        List<ScoredChunk> reranked = rerankService.rerank(query, fused, topK);

        long elapsed = System.currentTimeMillis() - start;
        log.info("Hybrid-rerank search 完成: topK={}, elapsed={}ms", topK, elapsed);

        return reranked;
    }

    private List<ScoredChunk> vectorSearch(String kbId, String query, int limit) {
        try {
            String queryEmbedding = toPgVector(doEmbed(query));
            List<ChunkBgeM3> chunks = chunkBgeM3Mapper.similaritySearch(kbId, queryEmbedding, limit);
            return IntStream.range(0, chunks.size())
                    .mapToObj(i -> {
                        ChunkBgeM3 c = chunks.get(i);
                        return ScoredChunk.builder()
                                .id(c.getId()).kbId(c.getKbId()).docId(c.getDocId())
                                .content(c.getContent()).metadata(c.getMetadata())
                                .source("vector")
                                .score(1.0 / (RRF_K + i + 1))
                                .build();
                    })
                    .toList();
        } catch (Exception e) {
            log.error("向量检索失败: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    private List<ScoredChunk> bm25Search(String kbId, String query, int limit) {
        try {
            List<ChunkBgeM3> chunks = chunkBgeM3Mapper.bm25Search(kbId, query, limit);
            return IntStream.range(0, chunks.size())
                    .mapToObj(i -> {
                        ChunkBgeM3 c = chunks.get(i);
                        return ScoredChunk.builder()
                                .id(c.getId()).kbId(c.getKbId()).docId(c.getDocId())
                                .content(c.getContent()).metadata(c.getMetadata())
                                .source("bm25")
                                .score(1.0 / (RRF_K + i + 1))
                                .build();
                    })
                    .toList();
        } catch (Exception e) {
            log.error("BM25 检索失败: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * Reciprocal Rank Fusion: RRF(d) = Σ 1/(k + rank_i(d))
     */
    private List<ScoredChunk> reciprocalRankFusion(
            List<ScoredChunk> vectorResults, List<ScoredChunk> bm25Results) {

        Map<String, ScoredChunk> chunkMap = new LinkedHashMap<>();
        Map<String, Double> rrfScores = new HashMap<>();

        for (int i = 0; i < vectorResults.size(); i++) {
            ScoredChunk c = vectorResults.get(i);
            rrfScores.merge(c.getId(), 1.0 / (RRF_K + i + 1), Double::sum);
            chunkMap.putIfAbsent(c.getId(), c);
        }
        for (int i = 0; i < bm25Results.size(); i++) {
            ScoredChunk c = bm25Results.get(i);
            rrfScores.merge(c.getId(), 1.0 / (RRF_K + i + 1), Double::sum);
            chunkMap.putIfAbsent(c.getId(), c);
        }

        return rrfScores.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .map(entry -> {
                    ScoredChunk original = chunkMap.get(entry.getKey());
                    return ScoredChunk.builder()
                            .id(original.getId()).kbId(original.getKbId()).docId(original.getDocId())
                            .content(original.getContent()).metadata(original.getMetadata())
                            .source("hybrid").score(entry.getValue())
                            .build();
                })
                .toList();
    }

    // ==================== 索引初始化 ====================

    @Override
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public void ensureIndexes() {
        // TSV 列 + GIN 索引（确保列创建成功后才创建索引，避免级联失败）
        try {
            log.info("正在初始化数据库索引...");
            chunkBgeM3Mapper.ensureTsvColumn();
            log.info("TSV 列已就绪");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("TSV 列已存在，跳过");
            } else {
                log.error("TSV 列创建失败，跳过后续索引初始化", e);
                return;
            }
        }
        try {
            chunkBgeM3Mapper.ensureTsvIndex();
            log.info("GIN 索引已就绪");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("GIN 索引已存在，跳过");
            } else {
                log.error("GIN 索引创建失败", e);
            }
        }
        // HNSW 向量索引（独立于 TSV/GIN，CREATE INDEX CONCURRENTLY 不能在事务中运行）
        try {
            chunkBgeM3Mapper.ensureHnswIndex();
            log.info("HNSW 索引已就绪");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("HNSW 索引已存在，跳过");
            } else {
                log.error("HNSW 索引创建失败", e);
            }
        }
    }

    // ==================== 工具方法 ====================

    private String toPgVector(float[] v) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            sb.append(v[i]);
            if (i < v.length - 1) sb.append(",");
        }
        sb.append("]");
        return sb.toString();
    }
}
