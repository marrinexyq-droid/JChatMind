package com.marrine.jchatmind.config;

import com.google.genai.Client;
import com.google.genai.types.HttpOptions;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.deepseek.DeepSeekChatModel;
import org.springframework.ai.google.genai.GoogleGenAiChatModel;
import org.springframework.ai.google.genai.GoogleGenAiChatOptions;
import org.springframework.ai.model.tool.ToolCallingManager;
import org.springframework.ai.zhipuai.ZhiPuAiChatModel;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.retry.support.RetryTemplate;

@Configuration
@EnableConfigurationProperties(GoogleGenAiChatProperties.class)
public class MultiChatClientConfig {
    // deepseek
    @Bean("deepseek-chat")
    public ChatClient deepSeekChatClient(DeepSeekChatModel deepSeekChatModel) {
        return ChatClient.create(deepSeekChatModel);
    }

    // zhipuai
    @Bean("glm-4.6")
    public ChatClient zhiPuAiChatClient(ZhiPuAiChatModel zhiPuAiChatModel) {
        return ChatClient.create(zhiPuAiChatModel);
    }

    @Bean("gemini-2.5-flash")
    @Conditional(GoogleGenAiApiKeyPresentCondition.class)
    public ChatClient googleGenAiChatClient(
            GoogleGenAiChatProperties properties,
            ToolCallingManager toolCallingManager,
            RetryTemplate retryTemplate,
            ObjectProvider<ObservationRegistry> observationRegistry) {
        Client genAiClient = Client.builder()
                .apiKey(properties.getApiKey())
                .vertexAI(false)
                .httpOptions(HttpOptions.builder()
                        .timeout(properties.getTimeoutMillis())
                        .build())
                .build();

        GoogleGenAiChatOptions options = GoogleGenAiChatOptions.builder()
                .model(properties.getModel())
                .temperature(properties.getTemperature())
                .maxOutputTokens(properties.getMaxOutputTokens())
                .build();

        GoogleGenAiChatModel chatModel = GoogleGenAiChatModel.builder()
                .genAiClient(genAiClient)
                .defaultOptions(options)
                .toolCallingManager(toolCallingManager)
                .retryTemplate(retryTemplate)
                .observationRegistry(observationRegistry.getIfUnique(() -> ObservationRegistry.NOOP))
                .build();

        return ChatClient.create(chatModel);
    }

}
