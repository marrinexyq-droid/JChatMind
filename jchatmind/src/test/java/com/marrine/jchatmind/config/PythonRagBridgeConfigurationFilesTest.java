package com.marrine.jchatmind.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.io.ClassPathResource;

import java.util.Properties;

import static org.junit.jupiter.api.Assertions.assertEquals;

class PythonRagBridgeConfigurationFilesTest {

    @Test
    void defaultProfileKeepsPythonBridgeDisabled() {
        Properties properties = load("application.yaml");

        assertEquals("false", properties.getProperty("rag.python-bridge.enabled"));
        assertEquals("false", properties.getProperty("rag.python-bridge.ingestion-enabled"));
        assertEquals("false", properties.getProperty("rag.python-bridge.readiness-gate-enabled"));
        assertEquals("15000", properties.getProperty("rag.python-bridge.readiness-cache-ttl-ms"));
        assertEquals("false", properties.getProperty("rag.python-bridge.canary-preflight-enabled"));
        assertEquals("false", properties.getProperty("rag.python-bridge.canary-preflight-fail-on-error"));
        assertEquals("java-rag-canary", properties.getProperty("rag.python-bridge.canary-preflight-collection"));
    }

    @Test
    void ragCanaryProfileEnablesGuardedPythonBridge() {
        Properties properties = load("application-rag-canary.yaml");

        assertEquals("rag-canary", properties.getProperty("spring.config.activate.on-profile"));
        assertEquals("true", properties.getProperty("rag.python-bridge.enabled"));
        assertEquals("true", properties.getProperty("rag.python-bridge.ingestion-enabled"));
        assertEquals("true", properties.getProperty("rag.python-bridge.readiness-gate-enabled"));
        assertEquals("true", properties.getProperty("rag.python-bridge.canary-preflight-enabled"));
        assertEquals("true", properties.getProperty("rag.python-bridge.canary-preflight-fail-on-error"));
        assertEquals("java-rag-canary", properties.getProperty("rag.python-bridge.canary-preflight-collection"));
        assertEquals("false", properties.getProperty("rag.python-bridge.fallback-on-error"));
        assertEquals("false", properties.getProperty("rag.python-bridge.fallback-on-empty"));
        assertEquals("true", properties.getProperty("rag.python-bridge.fail-on-ingestion-error"));
    }

    private Properties load(String resourceName) {
        YamlPropertiesFactoryBean factory = new YamlPropertiesFactoryBean();
        factory.setResources(new ClassPathResource(resourceName));
        return factory.getObject();
    }
}
