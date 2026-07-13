package com.marrine.jchatmind.config;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class ApplicationConfigurationSecurityTest {

    @Test
    void applicationYamlMustNotContainUsableSecretDefaults() throws IOException {
        String yaml = Files.readString(Path.of("src/main/resources/application.yaml"));

        for (String variable : new String[]{
                "DB_PASSWORD",
                "MAIL_PASSWORD",
                "DEEPSEEK_API_KEY",
                "ZHIPUAI_API_KEY"
        }) {
            assertThat(yaml.contains(variable + ":"))
                    .as("%s must not have a default value", variable)
                    .isFalse();
        }
    }
}
