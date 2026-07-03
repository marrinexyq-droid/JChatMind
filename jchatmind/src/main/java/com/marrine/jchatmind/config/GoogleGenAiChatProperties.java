package com.marrine.jchatmind.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "spring.ai.google.genai")
public class GoogleGenAiChatProperties {

    private String apiKey;

    private String model = "gemini-2.5-flash";

    private Double temperature = 0.7;

    private Integer maxOutputTokens = 2048;

    private Integer timeoutMillis = 30000;
}
