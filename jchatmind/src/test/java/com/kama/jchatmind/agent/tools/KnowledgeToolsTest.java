package com.kama.jchatmind.agent.tools;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class KnowledgeToolsTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void contextParameterIsOptionalInToolSchema() throws Exception {
        ToolCallback callback = MethodToolCallbackProvider.builder()
                .toolObjects(new KnowledgeTools(null, null))
                .build()
                .getToolCallbacks()[0];

        JsonNode schema = objectMapper.readTree(callback.getToolDefinition().inputSchema());
        JsonNode properties = schema.path("properties");
        List<String> required = new ArrayList<>();
        schema.path("required").forEach(node -> required.add(node.asText()));

        assertTrue(properties.has("kbsId"));
        assertTrue(properties.has("query"));
        assertTrue(properties.has("context"));
        assertTrue(required.contains("kbsId"));
        assertTrue(required.contains("query"));
        assertFalse(required.contains("context"));
    }
}
