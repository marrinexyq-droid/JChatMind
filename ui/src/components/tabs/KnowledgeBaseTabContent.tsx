import React, { useMemo } from "react";
import { Button, Divider } from "antd";
import { PlusOutlined, BookOutlined } from "@ant-design/icons";
import type { KnowledgeBase } from "../../types";
import { getKnowledgeBaseEmoji } from "../../utils";

interface KnowledgeBaseTabContentProps {
  knowledgeBases: KnowledgeBase[];
  onCreateKnowledgeBaseClick?: () => void;
  onSelectKnowledgeBase?: (knowledgeBaseId: string) => void;
}

const KnowledgeBaseTabContent: React.FC<KnowledgeBaseTabContentProps> = ({
  knowledgeBases,
  onCreateKnowledgeBaseClick,
  onSelectKnowledgeBase,
}) => {
  // 为每个知识库生成 emoji
  const knowledgeBasesWithEmoji = useMemo(() => {
    return knowledgeBases.map((kb) => ({
      ...kb,
      emoji: getKnowledgeBaseEmoji(kb.knowledgeBaseId),
    }));
  }, [knowledgeBases]);

  return (
    <div className="flex flex-col h-full">
      <Button
        color="purple"
        variant="filled"
        icon={<PlusOutlined />}
        onClick={onCreateKnowledgeBaseClick}
        className="w-full"
        style={{
          background: "linear-gradient(135deg, rgba(167, 139, 250, 0.25), rgba(192, 132, 252, 0.2))",
          border: "1px solid rgba(167, 139, 250, 0.3)",
          fontWeight: 600,
        }}
      >
        新建知识库
      </Button>
      <Divider />
      <div className="flex-1 overflow-y-scroll rounded-xl">
        {knowledgeBases.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-purple-400">
            <BookOutlined className="text-4xl mb-2" />
            <p className="text-sm">暂无知识库</p>
            <p className="text-xs mt-1">点击上方按钮创建</p>
          </div>
        ) : (
          <div className="space-y-1.5 p-1.5">
            {knowledgeBasesWithEmoji.map((kb) => (
              <div
                key={kb.knowledgeBaseId}
                onClick={() => onSelectKnowledgeBase?.(kb.knowledgeBaseId)}
                className="w-full px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 ease-out glass-solid glass-hover"
                style={{
                  transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                }}
              >
                <div className="flex items-start gap-3">
                  <div
                    className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-lg mt-0.5"
                    style={{
                      background: "linear-gradient(135deg, #a78bfa 0%, #67e8f9 100%)",
                      boxShadow: "0 2px 8px rgba(167, 139, 250, 0.2)",
                    }}
                  >
                    {kb.emoji}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-purple-100 truncate text-sm">
                      {kb.name}
                    </div>
                    {kb.description && (
                      <div className="text-xs text-purple-300 mt-1 line-clamp-2">
                        {kb.description}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseTabContent;
