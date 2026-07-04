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
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DocumentFacadeServiceImplTest {

    @Test
    void uploadDocumentCallsPythonIngestionAfterFileIsStored() throws Exception {
        DocumentMapper documentMapper = mock(DocumentMapper.class);
        DocumentStorageService storageService = mock(DocumentStorageService.class);
        PythonRagIngestionClient ingestionClient = mock(PythonRagIngestionClient.class);
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

        DocumentFacadeServiceImpl service = new DocumentFacadeServiceImpl(
                documentMapper,
                new DocumentConverter(new ObjectMapper()),
                storageService,
                mock(MarkdownParserService.class),
                mock(GeminiDocParser.class),
                mock(RagService.class),
                mock(ChunkBgeM3Mapper.class),
                mock(GraphRagService.class),
                ingestionClient
        );

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
        DocumentMapper documentMapper = mock(DocumentMapper.class);
        DocumentStorageService storageService = mock(DocumentStorageService.class);
        PythonRagIngestionClient ingestionClient = mock(PythonRagIngestionClient.class);

        when(documentMapper.insert(any(Document.class))).thenAnswer(invocation -> {
            Document document = invocation.getArgument(0);
            document.setId("doc-1");
            return 1;
        });
        when(storageService.saveFile(any(), any(), any())).thenReturn("kb/doc-1/note.txt");
        when(ingestionClient.isEnabled()).thenReturn(false);

        DocumentFacadeServiceImpl service = new DocumentFacadeServiceImpl(
                documentMapper,
                new DocumentConverter(new ObjectMapper()),
                storageService,
                mock(MarkdownParserService.class),
                mock(GeminiDocParser.class),
                mock(RagService.class),
                mock(ChunkBgeM3Mapper.class),
                mock(GraphRagService.class),
                ingestionClient
        );

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
}
