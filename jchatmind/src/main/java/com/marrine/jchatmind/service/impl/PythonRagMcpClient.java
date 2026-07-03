package com.marrine.jchatmind.service.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.RagTrace;
import com.marrine.jchatmind.model.vo.RagTraceChunk;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.stream.IntStream;

@Service
@Slf4j
@RequiredArgsConstructor
public class PythonRagMcpClient {
    private final PythonRagBridgeProperties properties;
    private final ObjectMapper objectMapper;

    public Optional<RagSearchResult> search(String kbId, QueryPlan queryPlan) {
        QueryPlan plan = normalizePlan(queryPlan);
        try {
            Process process = new ProcessBuilder(command())
                    .directory(properties.resolvedProjectRoot().toFile())
                    .redirectError(ProcessBuilder.Redirect.PIPE)
                    .start();
            String request = buildToolCall(kbId, plan) + System.lineSeparator();
            process.getOutputStream().write(request.getBytes(StandardCharsets.UTF_8));
            process.getOutputStream().close();
            CompletableFuture<String> stdoutFuture = readAsync(process.getInputStream());
            CompletableFuture<String> stderrFuture = readAsync(process.getErrorStream());

            boolean finished = process.waitFor(properties.getTimeoutMs(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                log.warn("Python RAG MCP query timed out after {}ms", properties.getTimeoutMs());
                return Optional.empty();
            }

            String stdout = stdoutFuture.get();
            String stderr = stderrFuture.get();
            if (process.exitValue() != 0) {
                log.warn("Python RAG MCP exited with code {}: {}", process.exitValue(), stderr.trim());
                return Optional.empty();
            }
            return parseResponse(stdout, kbId, plan);
        } catch (IOException e) {
            log.warn("Python RAG MCP query failed: {}", e.getMessage());
            return Optional.empty();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.warn("Python RAG MCP query interrupted");
            return Optional.empty();
        } catch (ExecutionException e) {
            log.warn("Python RAG MCP output read failed: {}", e.getMessage());
            return Optional.empty();
        }
    }

    Optional<RagSearchResult> parseResponse(String stdout, String kbId, QueryPlan plan) throws IOException {
        String line = stdout.lines()
                .filter(value -> !value.isBlank())
                .findFirst()
                .orElse("");
        if (line.isBlank()) {
            return Optional.empty();
        }

        JsonNode root = objectMapper.readTree(line);
        if (root.has("error")) {
            log.warn("Python RAG MCP returned error: {}", root.path("error").path("message").asText());
            return Optional.empty();
        }

        JsonNode structured = root.path("result").path("structuredContent");
        JsonNode citations = structured.path("citations");
        if (!citations.isArray()) {
            return Optional.empty();
        }

        List<ScoredChunk> chunks = new ArrayList<>();
        for (JsonNode citation : citations) {
            String chunkId = citation.path("chunk_id").asText("");
            String docId = citation.path("document_id").asText("");
            String text = citation.path("text").asText("");
            if (chunkId.isBlank() || text.isBlank()) {
                continue;
            }
            chunks.add(ScoredChunk.builder()
                    .id(chunkId)
                    .kbId(kbId)
                    .docId(docId)
                    .content(text)
                    .metadata(citation.path("metadata").isMissingNode()
                            ? "{}"
                            : citation.path("metadata").toString())
                    .source("python-mcp:" + citation.path("source").asText("unknown"))
                    .score(citation.path("score").asDouble(0.0))
                    .build());
        }

        return Optional.of(RagSearchResult.builder()
                .chunks(chunks)
                .trace(buildTrace(kbId, plan, chunks))
                .build());
    }

    private String buildToolCall(String kbId, QueryPlan plan) throws IOException {
        ObjectNode arguments = objectMapper.createObjectNode();
        arguments.put("query", plan.effectiveSearchQuery());
        arguments.put("collection", kbId);
        arguments.put("top_k", plan.effectiveTopK());
        arguments.put("mode", plan.effectiveMode());

        ObjectNode params = objectMapper.createObjectNode();
        params.put("name", "query_knowledge_hub");
        params.set("arguments", arguments);

        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("id", "java-rag-bridge");
        request.put("method", "tools/call");
        request.set("params", params);
        return objectMapper.writeValueAsString(request);
    }

    private List<String> command() {
        Path main = properties.resolvedProjectRoot().resolve("main.py");
        List<String> command = new ArrayList<>();
        command.add(properties.getPythonExecutable());
        command.addAll(properties.getPythonArgs());
        command.add(main.toString());
        return command;
    }

    private CompletableFuture<String> readAsync(java.io.InputStream inputStream) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException e) {
                throw new IllegalStateException(e);
            }
        });
    }

    private QueryPlan normalizePlan(QueryPlan queryPlan) {
        if (queryPlan != null) {
            return queryPlan;
        }
        return QueryPlan.builder()
                .originalQuery("")
                .searchQuery("")
                .mode("hybrid")
                .topK(5)
                .candidatePoolSize(20)
                .build();
    }

    private RagTrace buildTrace(String kbId, QueryPlan plan, List<ScoredChunk> chunks) {
        List<RagTraceChunk> finalChunks = IntStream.range(0, chunks.size())
                .mapToObj(index -> {
                    ScoredChunk chunk = chunks.get(index);
                    return RagTraceChunk.builder()
                            .citationId("C" + (index + 1))
                            .id(chunk.getId())
                            .kbId(kbId)
                            .docId(chunk.getDocId())
                            .documentName(chunk.getDocId())
                            .contentPreview(preview(chunk.getContent()))
                            .metadata(chunk.getMetadata())
                            .matchedBy(List.of("python-mcp"))
                            .rrfRank(index + 1)
                            .rrfScore(chunk.getScore())
                            .finalRank(index + 1)
                            .build();
                })
                .toList();
        return RagTrace.builder()
                .query(plan.effectiveSearchQuery())
                .originalQuery(plan.getOriginalQuery())
                .plannedQuery(plan.effectiveSearchQuery())
                .queryType(plan.getQueryType() == null ? null : plan.getQueryType().name())
                .kbId(kbId)
                .mode("python-mcp:" + plan.effectiveMode())
                .topK(plan.effectiveTopK())
                .candidatePoolSize(plan.effectiveCandidatePoolSize())
                .vectorWeight(plan.effectiveVectorWeight())
                .bm25Weight(plan.effectiveBm25Weight())
                .graphExpansionEnabled(false)
                .graphMaxHops(0)
                .rerankApplied("hybrid-rerank".equals(plan.effectiveMode()))
                .rerankFallback(false)
                .vectorResults(List.of())
                .bm25Results(List.of())
                .rrfResults(finalChunks)
                .graphExpandedChunks(List.of())
                .rerankResults(List.of())
                .finalChunks(finalChunks)
                .build();
    }

    private String preview(String content) {
        if (content == null) {
            return "";
        }
        String compact = content.replaceAll("\\s+", " ").trim();
        return compact.length() <= 260 ? compact : compact.substring(0, 260) + "...";
    }
}
