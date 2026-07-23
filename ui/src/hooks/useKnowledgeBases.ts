import { createContext, useContext } from "react";
import type { CreateKnowledgeBaseRequest } from "../api/api.ts";
import type { KnowledgeBase } from "../types";

export interface KnowledgeBaseContextValue {
  knowledgeBases: KnowledgeBase[];
  createKnowledgeBaseHandle: (
    request: CreateKnowledgeBaseRequest,
  ) => Promise<void>;
}

export const KnowledgeBaseContext = createContext<
  KnowledgeBaseContextValue | undefined
>(undefined);

export function useKnowledgeBases(): KnowledgeBaseContextValue {
  const context = useContext(KnowledgeBaseContext);
  if (context === undefined) {
    throw new Error(
      "useKnowledgeBases must be used within a KnowledgeBaseProvider",
    );
  }
  return context;
}
