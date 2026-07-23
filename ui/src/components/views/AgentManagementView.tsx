import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Popconfirm, Empty, Typography, message } from "antd";
import {
  RobotOutlined, PlusOutlined, EditOutlined, DeleteOutlined, MessageOutlined,
} from "@ant-design/icons";
import { useAgents } from "../../hooks/useAgents.ts";
import { getAgentEmoji } from "../../utils";
import type { AgentVO } from "../../api/api.ts";

const { Title, Text, Paragraph } = Typography;

const cardStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--glass-border)",
  borderRadius: "16px",
};

interface AgentManagementViewProps {
  onCreateClick: () => void;
  onEditClick: (agent: AgentVO) => void;
  onDeleteClick: (agentId: string) => Promise<void>;
}

export default function AgentManagementView({ onCreateClick, onEditClick, onDeleteClick }: AgentManagementViewProps) {
  const navigate = useNavigate();
  const { agents } = useAgents();

  const agentsWithEmoji = useMemo(() => {
    return agents.map((agent) => ({ ...agent, emoji: getAgentEmoji(agent.id) }));
  }, [agents]);

  return (
    <div className="flex flex-col h-full p-6 overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto">
        <div className="flex items-center justify-between mb-4">
          <Title level={3} className="m-0" style={{ color: "var(--text-primary)", fontFamily: "var(--font-display)" }}>
            智能体管理
          </Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={onCreateClick}
            style={{ borderRadius: "12px", fontWeight: 600 }}>
            新建智能体
          </Button>
        </div>

        {agentsWithEmoji.length === 0 ? (
          <Empty
            image={<RobotOutlined style={{ fontSize: 48, color: "var(--text-muted)" }} />}
            description={<span style={{ color: "var(--text-secondary)" }}>暂无智能体，点击上方按钮创建</span>}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agentsWithEmoji.map((agent) => (
              <div key={agent.id} className="p-4 rounded-2xl transition-all duration-200" style={cardStyle}>
                <div className="flex items-start gap-3">
                  <div
                    className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 text-2xl"
                    style={{ background: "linear-gradient(135deg, #8b9cf7 0%, #67e8f9 100%)" }}
                  >
                    {agent.emoji}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm mb-0.5" style={{ color: "var(--text-primary)" }}>
                      {agent.name}
                    </div>
                    {agent.description && (
                      <Paragraph className="text-xs m-0 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                        {agent.description}
                      </Paragraph>
                    )}
                    <Text className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {agent.model || "默认模型"}
                    </Text>
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-3 pt-3" style={{ borderTop: "1px solid var(--glass-border)" }}>
                  <button
                    onClick={() => navigate("/chat")}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                    style={{ color: "var(--accent-blue)", background: "rgba(139,156,247,0.08)" }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "rgba(139,156,247,0.15)"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "rgba(139,156,247,0.08)"}
                  >
                    <MessageOutlined /> 开始对话
                  </button>
                  <button
                    onClick={() => onEditClick(agent)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                    style={{ color: "var(--text-secondary)", background: "rgba(255,255,255,0.04)" }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
                  >
                    <EditOutlined className="mr-1" />编辑
                  </button>
                  <Popconfirm
                    title="确定要删除这个智能体吗？"
                    onConfirm={async () => {
                      await onDeleteClick(agent.id);
                      message.success("删除成功");
                    }}
                    okText="确定" cancelText="取消"
                  >
                    <button
                      className="px-2 py-1.5 rounded-lg text-xs transition-colors"
                      style={{ color: "var(--text-muted)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(251,113,133,0.1)"; e.currentTarget.style.color = "#fb7185"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-muted)"; }}
                    >
                      <DeleteOutlined />
                    </button>
                  </Popconfirm>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
