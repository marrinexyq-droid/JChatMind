package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.request.CreateChatSessionRequest;
import com.marrine.jchatmind.model.request.UpdateChatSessionRequest;
import com.marrine.jchatmind.model.response.CreateChatSessionResponse;
import com.marrine.jchatmind.model.response.GetChatSessionResponse;
import com.marrine.jchatmind.model.response.GetChatSessionsResponse;

public interface ChatSessionFacadeService {
    GetChatSessionsResponse getChatSessions();

    GetChatSessionResponse getChatSession(String chatSessionId);

    GetChatSessionsResponse getChatSessionsByAgentId(String agentId);

    CreateChatSessionResponse createChatSession(CreateChatSessionRequest request);

    void deleteChatSession(String chatSessionId);

    void updateChatSession(String chatSessionId, UpdateChatSessionRequest request);
}
