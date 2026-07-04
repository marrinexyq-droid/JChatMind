package com.marrine.jchatmind.config;

import org.junit.jupiter.api.Test;
import org.springframework.ai.deepseek.DeepSeekChatModel;
import org.springframework.ai.model.tool.ToolCallingManager;
import org.springframework.ai.zhipuai.ZhiPuAiChatModel;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.retry.support.RetryTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class MultiChatClientConfigTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(MultiChatClientConfig.class)
            .withBean(DeepSeekChatModel.class, () -> mock(DeepSeekChatModel.class))
            .withBean(ZhiPuAiChatModel.class, () -> mock(ZhiPuAiChatModel.class))
            .withBean(ToolCallingManager.class, () -> mock(ToolCallingManager.class))
            .withBean(RetryTemplate.class, RetryTemplate::new);

    @Test
    void doesNotRegisterGeminiClientWithoutApiKey() {
        contextRunner
                .withPropertyValues("spring.ai.google.genai.api-key=")
                .run(context -> {
                    assertThat(context).hasBean("deepseek-chat");
                    assertThat(context).hasBean("glm-4.6");
                    assertThat(context).doesNotHaveBean("gemini-2.5-flash");
                });
    }

    @Test
    void registersGeminiClientWhenApiKeyIsConfigured() {
        contextRunner
                .withPropertyValues("spring.ai.google.genai.api-key=test-key")
                .run(context -> {
                    assertThat(context).hasBean("deepseek-chat");
                    assertThat(context).hasBean("glm-4.6");
                    assertThat(context).hasBean("gemini-2.5-flash");
                });
    }
}
