package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.request.CreateKnowledgeBaseRequest;
import com.marrine.jchatmind.model.request.UpdateKnowledgeBaseRequest;
import com.marrine.jchatmind.model.response.CreateKnowledgeBaseResponse;
import com.marrine.jchatmind.model.response.GetKnowledgeBasesResponse;

public interface KnowledgeBaseFacadeService {
    GetKnowledgeBasesResponse getKnowledgeBases();

    CreateKnowledgeBaseResponse createKnowledgeBase(CreateKnowledgeBaseRequest request);

    void deleteKnowledgeBase(String knowledgeBaseId);

    void updateKnowledgeBase(String knowledgeBaseId, UpdateKnowledgeBaseRequest request);
}

