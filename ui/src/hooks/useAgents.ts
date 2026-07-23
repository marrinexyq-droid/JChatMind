import { createContext, useContext } from "react";
import type {
  AgentVO,
  CreateAgentRequest,
  UpdateAgentRequest,
} from "../api/api.ts";

export interface AgentsContextValue {
  agents: AgentVO[];
  createAgentHandle: (agent: CreateAgentRequest) => Promise<void>;
  deleteAgentHandle: (agentId: string) => Promise<void>;
  updateAgentHandle: (
    agentId: string,
    request: UpdateAgentRequest,
  ) => Promise<void>;
  refreshAgents: () => Promise<void>;
}

export const AgentsContext = createContext<AgentsContextValue | undefined>(
  undefined,
);

export function useAgents(): AgentsContextValue {
  const context = useContext(AgentsContext);
  if (context === undefined) {
    throw new Error("useAgents must be used within an AgentProvider");
  }
  return context;
}
