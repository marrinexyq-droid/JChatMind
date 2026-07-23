import { useEffect, useState, useCallback } from "react";
import {
  createKnowledgeBase,
  type CreateKnowledgeBaseRequest,
  getKnowledgeBases,
} from "../api/api.ts";
import type { KnowledgeBase } from "../types";
import { KnowledgeBaseContext } from "./useKnowledgeBases.ts";

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
