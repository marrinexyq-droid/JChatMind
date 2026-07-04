package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.config.PythonRagBridgeProperties;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PythonRagIngestionClientTest {

    @Test
    void disabledIngestionSkipsProcessAndReturnsSuccess() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setPythonExecutable("missing-python-executable");
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);

        assertTrue(client.ingest("kb", Path.of("doc.md")));
    }

    @Test
    void commandInvokesIngestScriptWithCollection() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setProjectRoot(Path.of("..", "rag-mcp").toString());
        properties.setPythonExecutable("py");
        properties.setPythonArgs(List.of("-3"));
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);
        Path source = Path.of("data/documents/kb/doc.md");

        List<String> command = client.command(source, "kb");

        assertEquals("py", command.get(0));
        assertEquals("-3", command.get(1));
        assertTrue(command.get(2).endsWith("rag-mcp\\scripts\\ingest.py")
                || command.get(2).endsWith("rag-mcp/scripts/ingest.py"));
        assertEquals(source.toAbsolutePath().normalize().toString(), command.get(3));
        assertEquals("--collection", command.get(4));
        assertEquals("kb", command.get(5));
    }

    @Test
    void deleteCommandInvokesDeleteScriptWithCollection() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setProjectRoot(Path.of("..", "rag-mcp").toString());
        properties.setPythonExecutable("py");
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);
        Path source = Path.of("data/documents/kb/doc.md");

        List<String> command = client.deleteCommand(source, "kb");

        assertEquals("py", command.get(0));
        assertTrue(command.get(1).endsWith("rag-mcp\\scripts\\delete_document.py")
                || command.get(1).endsWith("rag-mcp/scripts/delete_document.py"));
        assertEquals(source.toAbsolutePath().normalize().toString(), command.get(2));
        assertEquals("--collection", command.get(3));
        assertEquals("kb", command.get(4));
    }

    @Test
    void enabledIngestionReturnsTrueWhenProcessSucceeds() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonArgs(List.of("-version"));
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);

        assertTrue(client.ingest("kb", Path.of("doc.md")));
    }

    @Test
    void enabledDeleteReturnsTrueWhenProcessSucceeds() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonArgs(List.of("-version"));
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);

        assertTrue(client.delete("kb", Path.of("doc.md")));
    }

    @Test
    void enabledIngestionReturnsFalseOnFailureWhenFailOpen() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonArgs(List.of("-badoption"));
        properties.setFailOnIngestionError(false);
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);

        assertFalse(client.ingest("kb", Path.of("doc.md")));
    }

    @Test
    void enabledIngestionThrowsOnFailureWhenFailClosed() {
        PythonRagBridgeProperties properties = enabledProperties();
        properties.setPythonArgs(List.of("-badoption"));
        properties.setFailOnIngestionError(true);
        PythonRagIngestionClient client = new PythonRagIngestionClient(properties);

        assertThrows(IllegalStateException.class, () -> client.ingest("kb", Path.of("doc.md")));
    }

    private PythonRagBridgeProperties enabledProperties() {
        PythonRagBridgeProperties properties = new PythonRagBridgeProperties();
        properties.setIngestionEnabled(true);
        properties.setProjectRoot(".");
        properties.setPythonExecutable(javaExecutable());
        properties.setIngestionTimeoutMs(5000);
        return properties;
    }

    private String javaExecutable() {
        String executable = System.getProperty("os.name").toLowerCase().contains("win")
                ? "java.exe"
                : "java";
        return Path.of(System.getProperty("java.home"), "bin", executable).toString();
    }
}
