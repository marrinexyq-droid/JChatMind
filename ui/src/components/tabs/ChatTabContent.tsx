import { useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Popconfirm } from "antd";
import { MessageOutlined, DeleteOutlined } from "@ant-design/icons";
import { useChatSessions } from "../../hooks/useChatSessions.ts";
import { useAgents } from "../../hooks/useAgents.tsx";

export default function ChatTabContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { chatSessions, loading, deleteChatSession } = useChatSessions();
  const { agents } = useAgents();

  const agentMap = useMemo(() => {
    const map = new Map<string, string>();
    agents.forEach((agent) => { map.set(agent.id, agent.name); });
    return map;
  }, [agents]);

  const getDisplayTitle = (session: { title?: string; agentId: string }) => {
    if (session.title) return session.title;
    const agentName = agentMap.get(session.agentId);
    return agentName ? `与 ${agentName} 的对话` : "新对话";
  };

  const currentChatId = location.pathname.startsWith("/chat/")
    ? location.pathname.split("/chat/")[1]
    : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>加载中...</span>
      </div>
    );
  }

  if (chatSessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2">
        <MessageOutlined style={{ fontSize: 24, color: "var(--text-muted)" }} />
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>暂无聊天记录</span>
      </div>
    );
  }

  return (
    <div className="space-y-0.5 px-2 py-1">
      {chatSessions.map((session) => {
        const active = currentChatId === session.id;
        return (
          <div
            key={session.id}
            onClick={() => navigate(`/chat/${session.id}`)}
            className="group flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm relative"
            style={{
              color: active ? "var(--text-primary)" : "var(--text-secondary)",
              background: active ? "var(--glass-bg-light)" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!active) {
                e.currentTarget.style.background = "var(--glass-bg-light)";
                e.currentTarget.style.color = "var(--color-accent)";
              }
            }}
            onMouseLeave={(e) => {
              if (!active) {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-secondary)";
              }
            }}
          >
            <MessageOutlined className="text-xs shrink-0"
              style={{ color: active ? "var(--color-primary)" : "var(--text-muted)" }} />
            <span className="flex-1 truncate">{getDisplayTitle(session)}</span>
            <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={(e) => e.stopPropagation()}>
              <Popconfirm
                title="确定要删除这条聊天记录吗？"
                onConfirm={() => deleteChatSession(session.id)}
                okText="确定" cancelText="取消"
              >
                <button
                  className="w-6 h-6 rounded flex items-center justify-center transition-colors"
                  style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(251,113,133,0.12)";
                    e.currentTarget.style.color = "#fb7185";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--text-muted)";
                  }}
                >
                  <DeleteOutlined className="text-xs" />
                </button>
              </Popconfirm>
            </div>
          </div>
        );
      })}
    </div>
  );
}