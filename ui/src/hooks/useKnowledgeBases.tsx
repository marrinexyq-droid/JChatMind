import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  createKnowledgeBase,
  type CreateKnowledgeBaseRequest,
  getKnowledgeBases,
} from "../api/api.ts";
import type { KnowledgeBase } from "../types";

interface KnowledgeBaseContextType {
  knowledgeBases: KnowledgeBase[];
  createKnowledgeBaseHandle: (
    request: CreateKnowledgeBaseRequest,
  ) => Promise<void>;
}

const KnowledgeBaseContext = createContext<
  KnowledgeBaseContextType | undefined
>(undefined);

export function KnowledgeBaseProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  useEffect(() => {
    async function fetchData() {
      const resp = await getKnowledgeBases();
      const converted = resp.knowledgeBases.map((kb) => ({
        knowledgeBaseId: kb.id,
        name: kb.name,
        description: kb.description || "",
      }));
      setKnowledgeBases(converted);
    }
    fetchData();
  }, []);

  const createKnowledgeBaseHandle = useCallback(
    async (request: CreateKnowledgeBaseRequest) => {
      await createKnowledgeBase(request);
      const resp = await getKnowledgeBases();
      const converted = resp.knowledgeBases.map((kb) => ({
        knowledgeBaseId: kb.id,
        name: kb.name,
        description: kb.description || "",
      }));
      setKnowledgeBases(converted);
    },
    [],
  );

  return (
    <KnowledgeBaseContext.Provider
      value={{ knowledgeBases, createKnowledgeBaseHandle }}
    >
      {children}
    </KnowledgeBaseContext.Provider>
  );
}

export function useKnowledgeBases(): KnowledgeBaseContextType {
  const context = useContext(KnowledgeBaseContext);
  if (context === undefined) {
    throw new Error(
      "useKnowledgeBases must be used within a KnowledgeBaseProvider",
    );
  }
  return context;
}
