package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

@Service
@Slf4j
@RequiredArgsConstructor
public class PythonRagIngestionClient {
    private final PythonRagBridgeProperties properties;

    public boolean isEnabled() {
        return properties.isIngestionEnabled();
    }

    public boolean ingest(String collection, Path sourcePath) {
        if (!properties.isIngestionEnabled()) {
            return true;
        }

        try {
            Process process = new ProcessBuilder(command(sourcePath, collection))
                    .directory(properties.resolvedProjectRoot().toFile())
                    .redirectError(ProcessBuilder.Redirect.PIPE)
                    .start();
            CompletableFuture<String> stdoutFuture = readAsync(process.getInputStream());
            CompletableFuture<String> stderrFuture = readAsync(process.getErrorStream());

            boolean finished = process.waitFor(properties.getIngestionTimeoutMs(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                return handleFailure("Python RAG ingestion timed out after "
                        + properties.getIngestionTimeoutMs() + "ms");
            }

            String stdout = stdoutFuture.get();
            String stderr = stderrFuture.get();
            if (process.exitValue() != 0) {
                return handleFailure("Python RAG ingestion exited with code "
                        + process.exitValue() + ": " + stderr.trim());
            }

            log.info("Python RAG ingestion completed for collection={}, sourcePath={}, output={}",
                    collection, sourcePath, compact(stdout));
            return true;
        } catch (IOException e) {
            return handleFailure("Python RAG ingestion failed: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return handleFailure("Python RAG ingestion interrupted", e);
        } catch (ExecutionException e) {
            return handleFailure("Python RAG ingestion output read failed: " + e.getMessage(), e);
        }
    }

    List<String> command(Path sourcePath, String collection) {
        Path ingestScript = properties.resolvedProjectRoot().resolve("scripts").resolve("ingest.py");
        List<String> command = new ArrayList<>();
        command.add(properties.getPythonExecutable());
        command.addAll(properties.getPythonArgs());
        command.add(ingestScript.toString());
        command.add(sourcePath.toAbsolutePath().normalize().toString());
        command.add("--collection");
        command.add(collection);
        return command;
    }

    private boolean handleFailure(String message) {
        return handleFailure(message, null);
    }

    private boolean handleFailure(String message, Exception cause) {
        if (properties.isFailOnIngestionError()) {
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
}
