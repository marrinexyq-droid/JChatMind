package com.marrine.jchatmind.service.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import com.marrine.jchatmind.model.vo.PythonRagBridgeReadiness;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.stream.IntStream;

@Service
@Slf4j
@RequiredArgsConstructor
public class PythonRagMcpClient {
    private static final String QUERY_ID = "java-rag-bridge";
    private static final String READINESS_INITIALIZE_ID = "java-rag-readiness-initialize";
    private static final String READINESS_TOOLS_ID = "java-rag-readiness-tools";
    private static final String READINESS_STATUS_ID = "java-rag-readiness-status";
    private static final Set<String> REQUIRED_TOOLS = Set.of(
            "query_knowledge_hub",
            "list_collections",
            "get_system_status",
            "get_document_summary"
    );

    private final PythonRagBridgeProperties properties;
    private final ObjectMapper objectMapper;

    public Optional<RagSearchResult> search(String kbId, QueryPlan queryPlan) {
        QueryPlan plan = normalizePlan(queryPlan);
        try {
            Optional<String> stdout = runMcpRequests(
                    List.of(buildToolCall(kbId, plan)),
                    properties.getTimeoutMs(),
                    "query"
            );
            if (stdout.isEmpty()) {
                return Optional.empty();
            }
            return parseResponse(stdout.get(), kbId, plan);
        } catch (IOException e) {
            log.warn("Python RAG MCP query failed: {}", e.getMessage());
            return Optional.empty();
        }
    }

    public Optional<PythonRagBridgeReadiness> checkReadiness() {
        try {
            Optional<String> stdout = runMcpRequests(
                    List.of(buildInitialize(), buildToolsList(), buildSystemStatusCall()),
                    properties.getTimeoutMs(),
                    "readiness"
            );
            if (stdout.isEmpty()) {
                return Optional.empty();
            }
            return parseReadinessResponse(stdout.get());
        } catch (IOException e) {
            log.warn("Python RAG MCP readiness check failed: {}", e.getMessage());
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

    Optional<PythonRagBridgeReadiness> parseReadinessResponse(String stdout) throws IOException {
        List<JsonNode> responses = parseJsonLines(stdout);
        if (responses.isEmpty()) {
            return Optional.empty();
        }
        Optional<JsonNode> error = responses.stream().filter(node -> node.has("error")).findFirst();
        if (error.isPresent()) {
            log.warn("Python RAG MCP readiness returned error: {}", error.get().path("error").path("message").asText());
            return Optional.empty();
        }

        JsonNode initialize = responseById(responses, READINESS_INITIALIZE_ID).orElse(null);
        JsonNode toolsResponse = responseById(responses, READINESS_TOOLS_ID).orElse(null);
        JsonNode statusResponse = responseById(responses, READINESS_STATUS_ID).orElse(null);
        if (initialize == null || toolsResponse == null || statusResponse == null) {
            return Optional.empty();
        }

        JsonNode serverInfo = initialize.path("result").path("serverInfo");
        List<String> tools = toolNames(toolsResponse.path("result").path("tools"));
        JsonNode status = statusResponse.path("result").path("structuredContent");
        if (status.isMissingNode() || status.path("status").asText("").isBlank()) {
            return Optional.empty();
        }

        List<String> collections = stringArray(status.path("collections"));
        Map<String, Integer> collectionChunkCounts = integerMap(status.path("collection_chunk_counts"));
        boolean requiredToolsPresent = tools.containsAll(REQUIRED_TOOLS);
        boolean ready = requiredToolsPresent && "ready".equals(status.path("status").asText());
        return Optional.of(PythonRagBridgeReadiness.builder()
                .ready(ready)
                .serverName(serverInfo.path("name").asText(""))
                .serverVersion(serverInfo.path("version").asText(""))
                .tools(tools)
                .collections(collections)
                .collectionChunkCounts(collectionChunkCounts)
                .totalChunks(status.path("total_chunks").asInt(0))
                .message(ready ? "ready" : "required MCP tools missing or status is not ready")
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
        request.put("id", QUERY_ID);
        request.put("method", "tools/call");
        request.set("params", params);
        return objectMapper.writeValueAsString(request);
    }

    private String buildInitialize() throws IOException {
        ObjectNode clientInfo = objectMapper.createObjectNode();
        clientInfo.put("name", "jchatmind-java-bridge");
        clientInfo.put("version", "1.8.0");

        ObjectNode params = objectMapper.createObjectNode();
        params.put("protocolVersion", "2024-11-05");
        params.set("clientInfo", clientInfo);

        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("id", READINESS_INITIALIZE_ID);
        request.put("method", "initialize");
        request.set("params", params);
        return objectMapper.writeValueAsString(request);
    }

    private String buildToolsList() throws IOException {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("id", READINESS_TOOLS_ID);
        request.put("method", "tools/list");
        return objectMapper.writeValueAsString(request);
    }

    private String buildSystemStatusCall() throws IOException {
        ObjectNode params = objectMapper.createObjectNode();
        params.put("name", "get_system_status");
        params.set("arguments", objectMapper.createObjectNode());

        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("id", READINESS_STATUS_ID);
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

    private Optional<String> runMcpRequests(List<String> requests, long timeoutMs, String operation) {
        try {
            Process process = new ProcessBuilder(command())
                    .directory(properties.resolvedProjectRoot().toFile())
                    .redirectError(ProcessBuilder.Redirect.PIPE)
                    .start();
            for (String request : requests) {
                process.getOutputStream().write((request + System.lineSeparator()).getBytes(StandardCharsets.UTF_8));
            }
            process.getOutputStream().close();
            CompletableFuture<String> stdoutFuture = readAsync(process.getInputStream());
            CompletableFuture<String> stderrFuture = readAsync(process.getErrorStream());

            boolean finished = process.waitFor(timeoutMs, TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                log.warn("Python RAG MCP {} timed out after {}ms", operation, timeoutMs);
                return Optional.empty();
            }

            String stdout = stdoutFuture.get();
            String stderr = stderrFuture.get();
            if (process.exitValue() != 0) {
                log.warn("Python RAG MCP {} exited with code {}: {}", operation, process.exitValue(), stderr.trim());
                return Optional.empty();
            }
            return Optional.of(stdout);
        } catch (IOException e) {
            log.warn("Python RAG MCP {} failed: {}", operation, e.getMessage());
            return Optional.empty();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.warn("Python RAG MCP {} interrupted", operation);
            return Optional.empty();
        } catch (ExecutionException e) {
            log.warn("Python RAG MCP {} output read failed: {}", operation, e.getMessage());
            return Optional.empty();
        }
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

    private List<JsonNode> parseJsonLines(String stdout) throws IOException {
        List<JsonNode> responses = new ArrayList<>();
        for (String line : stdout.lines().filter(value -> !value.isBlank()).toList()) {
            responses.add(objectMapper.readTree(line));
        }
        return responses;
    }

    private Optional<JsonNode> responseById(List<JsonNode> responses, String id) {
        return responses.stream()
                .filter(node -> id.equals(node.path("id").asText()))
                .findFirst();
    }

    private List<String> toolNames(JsonNode toolsNode) {
        List<String> tools = new ArrayList<>();
        if (!toolsNode.isArray()) {
            return tools;
        }
        for (JsonNode tool : toolsNode) {
            String name = tool.path("name").asText("");
            if (!name.isBlank()) {
                tools.add(name);
            }
        }
        return tools;
    }

    private List<String> stringArray(JsonNode arrayNode) {
        List<String> values = new ArrayList<>();
        if (!arrayNode.isArray()) {
            return values;
        }
        for (JsonNode value : arrayNode) {
            values.add(value.asText());
        }
        return values;
    }

    private Map<String, Integer> integerMap(JsonNode objectNode) {
        Map<String, Integer> values = new LinkedHashMap<>();
        if (!objectNode.isObject()) {
            return values;
        }
        objectNode.fields().forEachRemaining(entry -> values.put(entry.getKey(), entry.getValue().asInt()));
        return values;
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
