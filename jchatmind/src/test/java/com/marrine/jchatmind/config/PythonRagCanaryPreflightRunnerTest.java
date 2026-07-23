package com.marrine.jchatmind.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PythonRagCanaryPreflightRunnerTest {

    @Test
    void disabledPreflightDoesNotStartProcess() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setPythonExecutable("missing-python-executable");
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(properties, new ObjectMapper());

        assertTrue(runner.runPreflight());
    }

    @Test
    void commandUsesConfiguredPythonArgsProjectRootAndCollection() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setProjectRoot(Path.of("..", "rag-mcp").toString());
        properties.setPythonExecutable("py");
        properties.setPythonArgs(List.of("-3"));
        properties.setCanaryPreflightCollection("kb-canary");
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(properties, new ObjectMapper());

        List<String> command = runner.command();

        assertEquals("py", command.get(0));
        assertEquals("-3", command.get(1));
        assertTrue(command.get(2).endsWith("rag-mcp\\scripts\\canary_smoke.py")
                || command.get(2).endsWith("rag-mcp/scripts/canary_smoke.py"));
        assertEquals("--collection", command.get(3));
        assertEquals("kb-canary", command.get(4));
        assertEquals("--require-chroma", command.get(5));
    }

    @Test
    void parseReportMapsPassedCanaryJson() throws Exception {
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(
                new PythonRagBridgeProperties(),
                new ObjectMapper()
        );
        String stdout = """
                {
                  "status": "passed",
                  "collection": "canary",
                  "chunk_count": 1,
                  "query": {"result_count": 1},
                  "traces": {"ingestion": 1, "query": 1}
                }
                """;

        Optional<PythonRagCanaryPreflightRunner.CanaryReport> report = runner.parseReport(stdout);

        assertTrue(report.isPresent());
        assertEquals("canary", report.get().collection());
        assertEquals(1, report.get().chunkCount());
        assertEquals(1, report.get().queryResultCount());
        assertEquals("{\"ingestion\":1,\"query\":1}", report.get().traceSummary());
    }

    @Test
    void parseReportRejectsFailedStatus() {
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(
                new PythonRagBridgeProperties(),
                new ObjectMapper()
        );

        assertThrows(IllegalStateException.class, () -> runner.parseReport("{\"status\":\"failed\"}"));
    }

    @Test
    void enabledPreflightReturnsFalseOnProcessFailureWhenFailOpen() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonExecutable("missing-python-executable");
        properties.setCanaryPreflightFailOnError(false);
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(properties, new ObjectMapper());

        assertFalse(runner.runPreflight());
    }

    @Test
    void enabledPreflightThrowsOnProcessFailureWhenFailClosed() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonExecutable("missing-python-executable");
        properties.setCanaryPreflightFailOnError(true);
        PythonRagCanaryPreflightRunner runner = new PythonRagCanaryPreflightRunner(properties, new ObjectMapper());

        assertThrows(IllegalStateException.class, runner::runPreflight);
    }

    private PythonRagBridgeProperties enabledProperties() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setCanaryPreflightEnabled(true);
        properties.setProjectRoot(".");
        properties.setCanaryPreflightTimeoutMs(1000);
        return properties;
    }
}
