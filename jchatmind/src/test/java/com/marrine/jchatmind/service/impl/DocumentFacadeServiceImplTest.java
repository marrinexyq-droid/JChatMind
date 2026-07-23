package com.marrine.jchatmind.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.marrine.jchatmind.converter.DocumentConverter;
import com.marrine.jchatmind.mapper.ChunkBgeM3Mapper;
import com.marrine.jchatmind.mapper.DocumentMapper;
import com.marrine.jchatmind.model.entity.Document;
import com.marrine.jchatmind.model.response.CreateDocumentResponse;
import com.marrine.jchatmind.service.DocumentStorageService;
import com.marrine.jchatmind.service.GraphRagService;
import com.marrine.jchatmind.service.MarkdownParserService;
import com.marrine.jchatmind.service.RagService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.InOrder;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DocumentFacadeServiceImplTest {
    @TempDir
    Path tempDir;

    private DocumentMapper documentMapper;
    private DocumentStorageService storageService;
    private PythonRagIngestionClient ingestionClient;
    private GraphRagService graphRagService;
    private MarkdownParserService markdownParserService;
    private RagService ragService;
    private ChunkBgeM3Mapper chunkMapper;
    private DocumentFacadeServiceImpl service;

    @BeforeEach
    void setUp() {
        documentMapper = mock(DocumentMapper.class);
        storageService = mock(DocumentStorageService.class);
        ingestionClient = mock(PythonRagIngestionClient.class);
        graphRagService = mock(GraphRagService.class);
        markdownParserService = mock(MarkdownParserService.class);
        ragService = mock(RagService.class);
        chunkMapper = mock(ChunkBgeM3Mapper.class);
        service = new DocumentFacadeServiceImpl(
                documentMapper,
                new DocumentConverter(new ObjectMapper()),
                storageService,
                markdownParserService,
                mock(GeminiDocParser.class),
                ragService,
                chunkMapper,
                graphRagService,
                ingestionClient
        );
    }

    @Test
    void uploadDocumentCallsPythonIngestionAfterFileIsStored() throws Exception {
        Path storedPath = Path.of("data/documents/kb/doc-1/note.txt").toAbsolutePath().normalize();

        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.txt");
        when(storageService.getFilePath("kb/doc-1/note.txt")).thenReturn(storedPath);
        when(ingestionClient.isEnabled()).thenReturn(true);
        when(ingestionClient.ingest("kb", storedPath)).thenReturn(true);

        CreateDocumentResponse response = service.uploadDocument(
                "kb",
                new MockMultipartFile("file", "note.txt", "text/plain", "hello".getBytes())
        );

        assertEquals("doc-1", response.getDocumentId());
        verify(storageService).saveFile(any(), any(), any());
        verify(documentMapper).updateById(any(Document.class));
        verify(ingestionClient).ingest("kb", storedPath);
    }

    @Test
    void uploadDocumentDoesNotResolvePythonPathWhenIngestionIsDisabled() throws Exception {
        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.txt");
        when(ingestionClient.isEnabled()).thenReturn(false);

        CreateDocumentResponse response = service.uploadDocument(
                "kb",
                new MockMultipartFile("file", "note.txt", "text/plain", "hello".getBytes())
        );

        assertEquals("doc-1", response.getDocumentId());
        verify(documentMapper).updateById(any(Document.class));
        verify(ingestionClient).isEnabled();
        verify(storageService, org.mockito.Mockito.never()).getFilePath(any());
        verify(ingestionClient, org.mockito.Mockito.never()).ingest(any(), any());
    }

    @Test
    void successfulPythonMarkdownIngestionSkipsLegacyChunkAndGraphDoubleWrite() throws Exception {
        Path storedPath = Path.of("data/documents/kb/doc-1/note.md").toAbsolutePath().normalize();
        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.md");
        when(storageService.getFilePath("kb/doc-1/note.md")).thenReturn(storedPath);
        when(ingestionClient.isEnabled()).thenReturn(true);
        when(ingestionClient.ingest("kb", storedPath)).thenReturn(true);

        service.uploadDocument(
                "kb",
                new MockMultipartFile("file", "note.md", "text/markdown", "# title\nbody".getBytes())
        );

        verify(ingestionClient).ingest("kb", storedPath);
        verify(storageService, times(1)).getFilePath("kb/doc-1/note.md");
        verify(markdownParserService, never()).parseMarkdown(any());
        verify(ragService, never()).embed(any());
        verify(chunkMapper, never()).insert(any());
        verify(graphRagService, never()).indexChunk(any(), any(), any(), any(), any());
    }

    @Test
    void failedFailClosedPythonIngestionRemovesStoredFileAndDocumentRecord() throws Exception {
        Path storedPath = Path.of("data/documents/kb/doc-1/note.md").toAbsolutePath().normalize();
        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.md");
        when(storageService.getFilePath("kb/doc-1/note.md")).thenReturn(storedPath);
        when(ingestionClient.isEnabled()).thenReturn(true);
        when(ingestionClient.ingest("kb", storedPath))
                .thenThrow(new IllegalStateException("python ingestion failed"));
        when(documentMapper.deleteById("doc-1")).thenReturn(1);

        assertThrows(
                IllegalStateException.class,
                () -> service.uploadDocument(
                        "kb",
                        new MockMultipartFile(
                                "file",
                                "note.md",
                                "text/markdown",
                                "# title\nbody".getBytes()
                        )
                )
        );

        verify(storageService).deleteFile("kb/doc-1/note.md");
        verify(documentMapper).deleteById("doc-1");
        verify(markdownParserService, never()).parseMarkdown(any());
    }

    @ParameterizedTest
    @ValueSource(booleans = {false, true})
    void nonCanonicalPythonIngestionKeepsOneLegacyMarkdownWrite(boolean ingestionEnabled) throws Exception {
        Path storedPath = Files.writeString(tempDir.resolve("note.md"), "# title\nbody");
        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.md");
        when(storageService.getFilePath("kb/doc-1/note.md")).thenReturn(storedPath);
        when(ingestionClient.isEnabled()).thenReturn(ingestionEnabled);
        if (ingestionEnabled) {
            when(ingestionClient.ingest("kb", storedPath)).thenReturn(false);
        }
        when(markdownParserService.parseMarkdown(any())).thenReturn(
                List.of(new MarkdownParserService.MarkdownSection("title", "body"))
        );
        when(ragService.embed("title\nbody")).thenReturn(new float[]{1.0f, 2.0f});
        when(chunkMapper.insert(any())).thenAnswer(invocation -> {
            com.marrine.jchatmind.model.entity.ChunkBgeM3 chunk = invocation.getArgument(0);
            chunk.setId("chunk-1");
            return 1;
        });

        service.uploadDocument(
                "kb",
                new MockMultipartFile("file", "note.md", "text/markdown", "# title\nbody".getBytes())
        );

        if (ingestionEnabled) {
            verify(ingestionClient).ingest("kb", storedPath);
        } else {
            verify(ingestionClient, never()).ingest(anyString(), any());
        }
        verify(markdownParserService, times(1)).parseMarkdown(any());
        verify(ragService, times(1)).embed("title\nbody");
        verify(chunkMapper, times(1)).insert(any());
        verify(graphRagService, times(1)).indexChunk(
                "kb", "doc-1", "chunk-1", "title", "body"
        );
    }

    @Test
    void deleteDocumentCallsPythonDeleteBeforeLocalFileDeletionWhenEnabled() throws Exception {
        Path storedPath = Path.of("data/documents/kb/doc-1/note.txt").toAbsolutePath().normalize();
        when(documentMapper.selectById("doc-1")).thenReturn(document("doc-1"));
        when(storageService.getFilePath("kb/doc-1/note.txt")).thenReturn(storedPath);
        when(ingestionClient.isEnabled()).thenReturn(true);
        when(ingestionClient.delete("kb", storedPath)).thenReturn(true);
        when(documentMapper.deleteById("doc-1")).thenReturn(1);

        service.deleteDocument("doc-1");

        InOrder inOrder = inOrder(ingestionClient, storageService, graphRagService, documentMapper);
        inOrder.verify(ingestionClient).delete("kb", storedPath);
        inOrder.verify(storageService).deleteFile("kb/doc-1/note.txt");
        inOrder.verify(graphRagService).deleteDocumentGraph("doc-1");
        inOrder.verify(documentMapper).deleteById("doc-1");
    }

    @Test
    void deleteDocumentDoesNotResolvePythonPathWhenIngestionIsDisabled() throws Exception {
        when(documentMapper.selectById("doc-1")).thenReturn(document("doc-1"));
        when(ingestionClient.isEnabled()).thenReturn(false);
        when(documentMapper.deleteById("doc-1")).thenReturn(1);

        service.deleteDocument("doc-1");

        verify(ingestionClient).isEnabled();
        verify(storageService, org.mockito.Mockito.never()).getFilePath(any());
        verify(ingestionClient, org.mockito.Mockito.never()).delete(any(), any());
        verify(storageService).deleteFile("kb/doc-1/note.txt");
    }

    private Document document(String id) {
        return Document.builder()
                .id(id)
                .kbId("kb")
                .filename("note.txt")
                .filetype("txt")
                .size(5L)
                .metadata("{\"filePath\":\"kb/doc-1/note.txt\"}")
                .build();
    }
}
