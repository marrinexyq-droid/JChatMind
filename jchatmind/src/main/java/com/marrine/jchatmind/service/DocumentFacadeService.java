package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.request.CreateDocumentRequest;
import com.marrine.jchatmind.model.request.UpdateDocumentRequest;
import com.marrine.jchatmind.model.response.CreateDocumentResponse;
import com.marrine.jchatmind.model.response.GetDocumentsResponse;
import org.springframework.web.multipart.MultipartFile;

public interface DocumentFacadeService {
    GetDocumentsResponse getDocuments();

    GetDocumentsResponse getDocumentsByKbId(String kbId);

    CreateDocumentResponse createDocument(CreateDocumentRequest request);

    CreateDocumentResponse uploadDocument(String kbId, MultipartFile file);

    void deleteDocument(String documentId);

    void updateDocument(String documentId, UpdateDocumentRequest request);
}
