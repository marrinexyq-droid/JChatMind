import { createContext, useContext } from "react";
import type { ChatSessionVO } from "../api/api.ts";

export interface ChatSessionsContextValue {
  chatSessions: ChatSessionVO[];
  loading: boolean;
  refreshChatSessions: () => Promise<void>;
  deleteChatSession: (chatSessionId: string) => Promise<void>;
}

export const ChatSessionsContext = createContext<
  ChatSessionsContextValue | undefined
>(undefined);

export function useChatSessions() {
  const context = useContext(ChatSessionsContext);
  if (context === undefined) {
    throw new Error(
      "useChatSessions must be used within a ChatSessionsProvider",
    );
  }
  return context;
}
