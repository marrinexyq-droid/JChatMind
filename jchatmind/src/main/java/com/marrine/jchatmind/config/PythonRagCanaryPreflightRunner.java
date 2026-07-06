package com.marrine.jchatmind.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

@Component
@Slf4j
@RequiredArgsConstructor
public class PythonRagCanaryPreflightRunner implements ApplicationRunner {
    private final PythonRagBridgeProperties properties;
    private final ObjectMapper objectMapper;

    @Override
    public void run(ApplicationArguments args) {
        runPreflight();
    }

    boolean runPreflight() {
        if (!properties.isCanaryPreflightEnabled()) {
            return true;
        }

        try {
            Process process = new ProcessBuilder(command())
                    .directory(properties.resolvedProjectRoot().toFile())
                    .redirectError(ProcessBuilder.Redirect.PIPE)
                    .start();
            CompletableFuture<String> stdoutFuture = readAsync(process.getInputStream());
            CompletableFuture<String> stderrFuture = readAsync(process.getErrorStream());

            boolean finished = process.waitFor(properties.getCanaryPreflightTimeoutMs(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                return handleFailure("Python RAG canary preflight timed out after "
                        + properties.getCanaryPreflightTimeoutMs() + "ms", null);
            }

            String stdout = stdoutFuture.get();
            String stderr = stderrFuture.get();
            if (process.exitValue() != 0) {
                return handleFailure("Python RAG canary preflight exited with code "
                        + process.exitValue() + ": " + compact(stderr), null);
            }

            CanaryReport report = parseReport(stdout)
                    .orElseThrow(() -> new IllegalStateException("Python RAG canary preflight report is empty"));
            log.info("Python RAG canary preflight passed: collection={}, chunks={}, results={}, traces={}",
                    report.collection(), report.chunkCount(), report.queryResultCount(), report.traceSummary());
            return true;
        } catch (IOException e) {
            return handleFailure("Python RAG canary preflight failed: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return handleFailure("Python RAG canary preflight interrupted", e);
        } catch (ExecutionException e) {
            return handleFailure("Python RAG canary preflight output read failed: " + e.getMessage(), e);
        } catch (RuntimeException e) {
            return handleFailure("Python RAG canary preflight report failed validation: " + e.getMessage(), e);
        }
    }

    List<String> command() {
        Path script = properties.resolvedProjectRoot().resolve("scripts").resolve("canary_smoke.py");
        List<String> command = new ArrayList<>();
        command.add(properties.getPythonExecutable());
        command.addAll(properties.getPythonArgs());
        command.add(script.toString());
        command.add("--collection");
        command.add(properties.getCanaryPreflightCollection());
        return command;
    }

    Optional<CanaryReport> parseReport(String stdout) throws IOException {
        if (stdout == null || stdout.isBlank()) {
            return Optional.empty();
        }

        JsonNode root = objectMapper.readTree(stdout);
        String status = root.path("status").asText("");
        if (!"passed".equals(status)) {
            throw new IllegalStateException("status=" + status);
        }
        String collection = root.path("collection").asText("");
        int chunkCount = root.path("chunk_count").asInt(0);
        int queryResultCount = root.path("query").path("result_count").asInt(0);
        String traceSummary = root.path("traces").toString();
        if (collection.isBlank() || chunkCount < 1 || queryResultCount < 1) {
            throw new IllegalStateException("missing collection, chunks, or query evidence");
        }
        return Optional.of(new CanaryReport(collection, chunkCount, queryResultCount, traceSummary));
    }

    private boolean handleFailure(String message, Exception cause) {
        if (properties.isCanaryPreflightFailOnError()) {
            throw new IllegalStateException(message, cause);
        }
        log.warn(message);
        return false;
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

    private String compact(String value) {
        if (value == null) {
            return "";
        }
        return value.replaceAll("\\s+", " ").trim();
    }

    record CanaryReport(String collection, int chunkCount, int queryResultCount, String traceSummary) {
    }
}
