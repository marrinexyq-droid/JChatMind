package com.marrine.jchatmind.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Data
@Component
@ConfigurationProperties(prefix = "rag.python-bridge")
public class PythonRagBridgeProperties {
    private boolean enabled = false;
    private String projectRoot = "../rag-mcp";
    private String pythonExecutable = "python";
    private List<String> pythonArgs = new ArrayList<>();
    private long timeoutMs = 8000;
    private boolean fallbackOnError = true;
    private boolean fallbackOnEmpty = true;

    public Path resolvedProjectRoot() {
        return Path.of(projectRoot).toAbsolutePath().normalize();
    }
}
