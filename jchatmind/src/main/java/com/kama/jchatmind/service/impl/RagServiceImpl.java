package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.mapper.ChunkBgeM3Mapper;
import com.kama.jchatmind.mapper.DocumentMapper;
import com.kama.jchatmind.model.entity.ChunkBgeM3;
import com.kama.jchatmind.model.entity.Document;
import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.RagTrace;
import com.kama.jchatmind.model.vo.RagTraceChunk;
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

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;

@Service
@Slf4j
public class RagServiceImpl implements RagService {

    private static final int RRF_K = 60;
    private static final int CANDIDATE_POOL_SIZE = 20;
    private static final int PREVIEW_LENGTH = 260;

    private final ExecutorService searchExecutor = Executors.newFixedThreadPool(4);

    private final WebClient webClient;
    private final ChunkBgeM3Mapper chunkBgeM3Mapper;
    private final DocumentMapper documentMapper;
    private final RerankService rerankService;

    public RagServiceImpl(WebClient.Builder builder,
                          ChunkBgeM3Mapper chunkBgeM3Mapper,
                          DocumentMapper documentMapper,
                          RerankService rerankService) {
        this.webClient = builder.baseUrl("http://localhost:11434").build();
        this.chunkBgeM3Mapper = chunkBgeM3Mapper;
        this.documentMapper = documentMapper;
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

    @Override
    public List<String> similaritySearch(String kbId, String title) {
        String queryEmbedding = toPgVector(doEmbed(title));
        List<ChunkBgeM3> chunks = chunkBgeM3Mapper.similaritySearch(kbId, queryEmbedding, 3);
        return chunks.stream().map(ChunkBgeM3::getContent).toList();
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
                .candidatePoolSize(CANDIDATE_POOL_SIZE)
                .vectorWeight(1.0)
                .bm25Weight(1.0)
                .build();
        return hybridSearchWithTrace(kbId, queryPlan);
    }

    @Override
    public RagSearchResult hybridSearchWithTrace(String kbId, QueryPlan queryPlan) {
        long start = System.currentTimeMillis();
        QueryPlan plan = normalizePlan(queryPlan);
        String query = plan.effectiveSearchQuery();
        int topK = plan.effectiveTopK();
        String mode = plan.effectiveMode();
        int candidatePoolSize = plan.effectiveCandidatePoolSize();
        double vectorWeight = plan.effectiveVectorWeight();
        double bm25Weight = plan.effectiveBm25Weight();

        if ("vector".equals(mode)) {
            List<ScoredChunk> vectorResults = vectorSearch(kbId, query, topK);
            RagTrace trace = buildTrace(kbId, plan, topK, mode, candidatePoolSize, vectorWeight, bm25Weight,
                    vectorResults, List.of(), vectorResults, List.of(), vectorResults, false);
            log.info("Vector-only search: topK={}, elapsed={}ms", topK, System.currentTimeMillis() - start);
            return RagSearchResult.builder().chunks(vectorResults).trace(trace).build();
        }

        CompletableFuture<List<ScoredChunk>> vectorFuture = CompletableFuture.supplyAsync(
                () -> vectorSearch(kbId, query, candidatePoolSize), searchExecutor);
        CompletableFuture<List<ScoredChunk>> bm25Future = CompletableFuture.supplyAsync(
                () -> bm25Search(kbId, query, candidatePoolSize), searchExecutor);

        CompletableFuture.allOf(vectorFuture, bm25Future).join();

        List<ScoredChunk> vectorResults = vectorFuture.join();
        List<ScoredChunk> bm25Results = bm25Future.join();
        List<ScoredChunk> fused = reciprocalRankFusion(vectorResults, bm25Results, vectorWeight, bm25Weight);

        log.info("Hybrid search: vector={}, bm25={}, fused={}",
                vectorResults.size(), bm25Results.size(), fused.size());

        if (fused.isEmpty()) {
            RagTrace trace = buildTrace(kbId, plan, topK, mode, candidatePoolSize, vectorWeight, bm25Weight,
                    vectorResults, bm25Results, fused, List.of(), List.of(), false);
            return RagSearchResult.builder().chunks(Collections.emptyList()).trace(trace).build();
        }

        if ("hybrid".equals(mode)) {
            List<ScoredChunk> topResults = fused.stream().limit(topK).toList();
            RagTrace trace = buildTrace(kbId, plan, topK, mode, candidatePoolSize, vectorWeight, bm25Weight,
                    vectorResults, bm25Results, fused, List.of(), topResults, false);
            log.info("Hybrid search (no rerank): topK={}, elapsed={}ms", topK, System.currentTimeMillis() - start);
            return RagSearchResult.builder().chunks(topResults).trace(trace).build();
        }

        List<ScoredChunk> reranked = rerankService.rerank(query, fused, topK);
        boolean rerankFallback = reranked.stream().anyMatch(c -> !"rerank".equals(c.getSource()));
        RagTrace trace = buildTrace(kbId, plan, topK, mode, candidatePoolSize, vectorWeight, bm25Weight,
                vectorResults, bm25Results, fused, reranked, reranked, rerankFallback);

        log.info("Hybrid-rerank search: topK={}, elapsed={}ms", topK, System.currentTimeMillis() - start);
        return RagSearchResult.builder().chunks(reranked).trace(trace).build();
    }

    private QueryPlan normalizePlan(QueryPlan queryPlan) {
        if (queryPlan == null) {
            return QueryPlan.builder()
                    .originalQuery("")
                    .searchQuery("")
                    .mode("hybrid")
                    .topK(5)
                    .candidatePoolSize(CANDIDATE_POOL_SIZE)
                    .vectorWeight(1.0)
                    .bm25Weight(1.0)
                    .build();
        }
        return queryPlan;
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
            log.error("Vector search failed: {}", e.getMessage());
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
            log.error("BM25 search failed: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    List<ScoredChunk> reciprocalRankFusion(
            List<ScoredChunk> vectorResults, List<ScoredChunk> bm25Results, double vectorWeight, double bm25Weight) {

        Map<String, ScoredChunk> chunkMap = new LinkedHashMap<>();
        Map<String, Double> rrfScores = new HashMap<>();

        for (int i = 0; i < vectorResults.size(); i++) {
            ScoredChunk c = vectorResults.get(i);
            rrfScores.merge(c.getId(), vectorWeight * (1.0 / (RRF_K + i + 1)), Double::sum);
            chunkMap.putIfAbsent(c.getId(), c);
        }
        for (int i = 0; i < bm25Results.size(); i++) {
            ScoredChunk c = bm25Results.get(i);
            rrfScores.merge(c.getId(), bm25Weight * (1.0 / (RRF_K + i + 1)), Double::sum);
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

    private RagTrace buildTrace(String kbId,
                                QueryPlan queryPlan,
                                int topK,
                                String mode,
                                int candidatePoolSize,
                                double vectorWeight,
                                double bm25Weight,
                                List<ScoredChunk> vectorResults,
                                List<ScoredChunk> bm25Results,
                                List<ScoredChunk> rrfResults,
                                List<ScoredChunk> rerankResults,
                                List<ScoredChunk> finalChunks,
                                boolean rerankFallback) {
        Map<String, Integer> vectorRanks = rankMap(vectorResults);
        Map<String, Integer> bm25Ranks = rankMap(bm25Results);
        Map<String, Integer> rrfRanks = rankMap(rrfResults);
        Map<String, Integer> rerankRanks = rankMap(rerankResults);
        Map<String, Double> rrfScores = scoreMap(rrfResults);
        Map<String, Double> rerankScores = scoreMap(rerankResults);
        Map<String, String> docNames = loadDocumentNames(vectorResults, bm25Results, rrfResults, rerankResults, finalChunks);

        List<RagTraceChunk> finalTraceChunks = IntStream.range(0, finalChunks.size())
                .mapToObj(i -> toTraceChunk(finalChunks.get(i), i + 1, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .toList();

        return RagTrace.builder()
                .query(queryPlan.effectiveSearchQuery())
                .originalQuery(queryPlan.getOriginalQuery())
                .plannedQuery(queryPlan.effectiveSearchQuery())
                .queryType(queryPlan.getQueryType() == null ? null : queryPlan.getQueryType().name())
                .kbId(kbId)
                .mode(mode)
                .topK(topK)
                .candidatePoolSize(candidatePoolSize)
                .vectorWeight(vectorWeight)
                .bm25Weight(bm25Weight)
                .rerankApplied("hybrid-rerank".equals(mode))
                .rerankFallback(rerankFallback)
                .vectorResults(toTraceChunks(vectorResults, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .bm25Results(toTraceChunks(bm25Results, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .rrfResults(toTraceChunks(rrfResults, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .rerankResults(toTraceChunks(rerankResults, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .finalChunks(finalTraceChunks)
                .build();
    }

    private List<RagTraceChunk> toTraceChunks(List<ScoredChunk> chunks,
                                             Map<String, Integer> vectorRanks,
                                             Map<String, Integer> bm25Ranks,
                                             Map<String, Integer> rrfRanks,
                                             Map<String, Integer> rerankRanks,
                                             Map<String, Double> rrfScores,
                                             Map<String, Double> rerankScores,
                                             Map<String, String> docNames) {
        return IntStream.range(0, chunks.size())
                .mapToObj(i -> toTraceChunk(chunks.get(i), null, vectorRanks, bm25Ranks, rrfRanks, rerankRanks, rrfScores, rerankScores, docNames))
                .toList();
    }

    private RagTraceChunk toTraceChunk(ScoredChunk chunk,
                                       Integer finalRank,
                                       Map<String, Integer> vectorRanks,
                                       Map<String, Integer> bm25Ranks,
                                       Map<String, Integer> rrfRanks,
                                       Map<String, Integer> rerankRanks,
                                       Map<String, Double> rrfScores,
                                       Map<String, Double> rerankScores,
                                       Map<String, String> docNames) {
        List<String> matchedBy = new ArrayList<>();
        if (vectorRanks.containsKey(chunk.getId())) {
            matchedBy.add("vector");
        }
        if (bm25Ranks.containsKey(chunk.getId())) {
            matchedBy.add("bm25");
        }

        Integer rerankRank = rerankRanks.get(chunk.getId());
        return RagTraceChunk.builder()
                .citationId(finalRank == null ? null : "C" + finalRank)
                .id(chunk.getId())
                .kbId(chunk.getKbId())
                .docId(chunk.getDocId())
                .documentName(docNames.getOrDefault(chunk.getDocId(), chunk.getDocId()))
                .contentPreview(preview(chunk.getContent()))
                .metadata(chunk.getMetadata())
                .matchedBy(matchedBy)
                .vectorRank(vectorRanks.get(chunk.getId()))
                .vectorScore(scoreForRank(vectorRanks.get(chunk.getId())))
                .bm25Rank(bm25Ranks.get(chunk.getId()))
                .bm25Score(scoreForRank(bm25Ranks.get(chunk.getId())))
                .rrfRank(rrfRanks.get(chunk.getId()))
                .rrfScore(rrfScores.get(chunk.getId()))
                .rerankRank(rerankRank)
                .rerankScore(rerankScores.get(chunk.getId()))
                .finalRank(finalRank)
                .build();
    }

    @SafeVarargs
    private Map<String, String> loadDocumentNames(List<ScoredChunk>... chunkGroups) {
        Map<String, String> docNames = new HashMap<>();
        for (List<ScoredChunk> chunks : chunkGroups) {
            for (ScoredChunk chunk : chunks) {
                String docId = chunk.getDocId();
                if (docId == null || docNames.containsKey(docId)) {
                    continue;
                }
                try {
                    Document document = documentMapper.selectById(docId);
                    docNames.put(docId, document != null && document.getFilename() != null
                            ? document.getFilename()
                            : docId);
                } catch (Exception e) {
                    log.warn("Failed to load document name for docId={}: {}", docId, e.getMessage());
                    docNames.put(docId, docId);
                }
            }
        }
        return docNames;
    }

    private Map<String, Integer> rankMap(List<ScoredChunk> chunks) {
        Map<String, Integer> ranks = new HashMap<>();
        for (int i = 0; i < chunks.size(); i++) {
            ranks.putIfAbsent(chunks.get(i).getId(), i + 1);
        }
        return ranks;
    }

    private Map<String, Double> scoreMap(List<ScoredChunk> chunks) {
        Map<String, Double> scores = new HashMap<>();
        for (ScoredChunk chunk : chunks) {
            scores.putIfAbsent(chunk.getId(), chunk.getScore());
        }
        return scores;
    }

    private Double scoreForRank(Integer rank) {
        return rank == null ? null : 1.0 / (RRF_K + rank);
    }

    private String preview(String content) {
        if (content == null) {
            return "";
        }
        String compact = content.replaceAll("\\s+", " ").trim();
        if (compact.length() <= PREVIEW_LENGTH) {
            return compact;
        }
        return compact.substring(0, PREVIEW_LENGTH) + "...";
    }

    @Override
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public void ensureIndexes() {
        try {
            log.info("Initializing database indexes...");
            chunkBgeM3Mapper.ensureTsvColumn();
            log.info("TSV column is ready");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("TSV column already exists");
            } else {
                log.error("Failed to create TSV column, skipping index initialization", e);
                return;
            }
        }
        try {
            chunkBgeM3Mapper.ensureTsvIndex();
            log.info("GIN index is ready");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("GIN index already exists");
            } else {
                log.error("Failed to create GIN index", e);
            }
        }
        try {
            chunkBgeM3Mapper.ensureHnswIndex();
            log.info("HNSW index is ready");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                log.info("HNSW index already exists");
            } else {
                log.error("Failed to create HNSW index", e);
            }
        }
    }

    private String toPgVector(float[] v) {
        return "[" + String.join(",",
                IntStream.range(0, v.length)
                        .mapToObj(i -> Float.toString(v[i]))
                        .toList()) + "]";
    }
}
