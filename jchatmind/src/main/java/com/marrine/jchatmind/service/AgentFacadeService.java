package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.request.CreateAgentRequest;
import com.marrine.jchatmind.model.request.UpdateAgentRequest;
import com.marrine.jchatmind.model.response.CreateAgentResponse;
import com.marrine.jchatmind.model.response.GetAgentsResponse;

public interface AgentFacadeService {
    GetAgentsResponse getAgents();

    CreateAgentResponse createAgent(CreateAgentRequest request);

    void deleteAgent(String agentId);

    void updateAgent(String agentId, UpdateAgentRequest request);
}
