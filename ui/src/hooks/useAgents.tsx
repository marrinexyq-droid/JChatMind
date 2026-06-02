import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  type AgentVO,
  createAgent,
  type CreateAgentRequest,
  getAgents,
  deleteAgent,
  updateAgent,
  type UpdateAgentRequest,
} from "../api/api.ts";

interface AgentsContextType {
  agents: AgentVO[];
  createAgentHandle: (agent: CreateAgentRequest) => Promise<void>;
  deleteAgentHandle: (agentId: string) => Promise<void>;
  updateAgentHandle: (
    agentId: string,
    request: UpdateAgentRequest,
  ) => Promise<void>;
  refreshAgents: () => Promise<void>;
}

const AgentsContext = createContext<AgentsContextType | undefined>(undefined);

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

export function useAgents(): AgentsContextType {
  const context = useContext(AgentsContext);
  if (context === undefined) {
    throw new Error("useAgents must be used within an AgentProvider");
  }
  return context;
}
