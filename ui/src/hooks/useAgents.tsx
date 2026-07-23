import { useEffect, useState, useCallback } from "react";
import {
  type AgentVO,
  createAgent,
  type CreateAgentRequest,
  getAgents,
  deleteAgent,
  updateAgent,
  type UpdateAgentRequest,
} from "../api/api.ts";
import { AgentsContext } from "./useAgents.ts";

export function AgentProvider({ children }: { children: React.ReactNode }) {
  const [agents, setAgents] = useState<AgentVO[]>([]);

  useEffect(() => {
    async function fetchData() {
      const resp = await getAgents();
      setAgents(resp.agents);
    }
    fetchData();
  }, []);

  const refreshAgents = useCallback(async () => {
    const resp = await getAgents();
    setAgents(resp.agents);
  }, []);

  const createAgentHandle = useCallback(
    async (agent: CreateAgentRequest) => {
      await createAgent(agent);
      await refreshAgents();
    },
    [refreshAgents],
  );

  const deleteAgentHandle = useCallback(
    async (agentId: string) => {
      await deleteAgent(agentId);
      await refreshAgents();
    },
    [refreshAgents],
  );

  const updateAgentHandle = useCallback(
    async (agentId: string, request: UpdateAgentRequest) => {
      await updateAgent(agentId, request);
      await refreshAgents();
    },
    [refreshAgents],
  );

  return (
    <AgentsContext.Provider
      value={{
        agents,
        createAgentHandle,
        deleteAgentHandle,
        updateAgentHandle,
        refreshAgents,
      }}
    >
      {children}
    </AgentsContext.Provider>
  );
}
