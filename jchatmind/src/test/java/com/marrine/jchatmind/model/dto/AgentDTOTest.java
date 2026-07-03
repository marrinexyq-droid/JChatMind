package com.marrine.jchatmind.model.dto;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class AgentDTOTest {

    @Test
    void resolvesGeminiModelType() {
        assertThat(AgentDTO.ModelType.fromModelName("gemini-2.5-flash"))
                .isEqualTo(AgentDTO.ModelType.GEMINI_2_5_FLASH);
    }
}
