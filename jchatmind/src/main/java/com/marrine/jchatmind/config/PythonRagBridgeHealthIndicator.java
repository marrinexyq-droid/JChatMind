package com.marrine.jchatmind.config;

import com.marrine.jchatmind.model.vo.PythonRagBridgeReadiness;
import com.marrine.jchatmind.service.impl.PythonRagMcpClient;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Component("pythonRagBridge")
@RequiredArgsConstructor
public class PythonRagBridgeHealthIndicator implements HealthIndicator {
    private final PythonRagBridgeProperties properties;
    private final PythonRagMcpClient pythonRagMcpClient;

    @Override
    public Health health() {
        if (!properties.isEnabled() && !properties.isIngestionEnabled()) {
            return Health.up()
                    .withDetail("enabled", false)
                    .withDetail("ingestionEnabled", false)
                    .withDetail("message", "Python RAG bridge disabled")
                    .build();
        }

        Optional<PythonRagBridgeReadiness> readiness = pythonRagMcpClient.checkReadiness();
        if (readiness.isEmpty()) {
            return Health.down()
                    .withDetail("enabled", properties.isEnabled())
                    .withDetail("ingestionEnabled", properties.isIngestionEnabled())
                    .withDetail("message", "Python RAG MCP readiness check failed")
                    .build();
        }

        PythonRagBridgeReadiness status = readiness.get();
        Health.Builder builder = status.isReady() ? Health.up() : Health.down();
        return builder
                .withDetail("enabled", properties.isEnabled())
                .withDetail("ingestionEnabled", properties.isIngestionEnabled())
                .withDetail("serverName", text(status.getServerName()))
                .withDetail("serverVersion", text(status.getServerVersion()))
                .withDetail("tools", list(status.getTools()))
                .withDetail("collections", list(status.getCollections()))
                .withDetail("collectionChunkCounts", map(status.getCollectionChunkCounts()))
                .withDetail("totalChunks", status.getTotalChunks())
                .withDetail("message", text(status.getMessage()))
                .build();
    }

    private String text(String value) {
        return value == null ? "" : value;
    }

    private List<String> list(List<String> value) {
        return value == null ? List.of() : value;
    }

    private Map<String, Integer> map(Map<String, Integer> value) {
        return value == null ? Map.of() : value;
    }
}
