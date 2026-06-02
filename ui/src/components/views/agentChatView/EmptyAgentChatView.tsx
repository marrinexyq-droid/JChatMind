import { useState, useMemo } from "react";
import { Select } from "antd";
import { DownOutlined, SendOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import {
  type AgentVO,
  createChatMessage,
  createChatSession,
} from "../../../api/api.ts";
import { getAgentEmoji } from "../../../utils";
import { useChatSessions } from "../../../hooks/useChatSessions.ts";

interface EmptyAgentChatViewProps {
  loading: boolean;
  agents: AgentVO[];
}

const suggestions = [
  { icon: "💡", text: "解释量子计算的基本原理" },
  { icon: "🚀", text: "帮我设计一个 REST API 架构" },
  { icon: "📝", text: "写一篇关于人工智能的博客" },
  { icon: "🔍", text: "分析这段代码的性能瓶颈" },
];

export default function EmptyAgentChatView({ loading, agents }: EmptyAgentChatViewProps) {
  const [message, setMessage] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const navigate = useNavigate();
  const { refreshChatSessions } = useChatSessions();

  const agentsWithEmoji = useMemo(() => {
    return agents.map((agent) => ({ ...agent, emoji: getAgentEmoji(agent.id) }));
  }, [agents]);

  const effectiveAgentId = useMemo(() => {
    if (selectedAgentId) return selectedAgentId;
    return agents.length > 0 ? agents[0].id : null;
  }, [selectedAgentId, agents]);

  const handleSend = async () => {
    if (!effectiveAgentId) return;
    const trimmed = message.trim();
    if (!trimmed) return;
    const response = await createChatSession({
      agentId: effectiveAgentId,
      title: trimmed.slice(0, 20),
    });
    await createChatMessage({
      sessionId: response.chatSessionId ?? "",
      content: trimmed,
      role: "user",
      agentId: effectiveAgentId,
    });
    await refreshChatSessions();
    setMessage("");
    navigate(`/chat/${response.chatSessionId}`);
  };

  return (
    <div className="flex flex-col items-center h-full overflow-y-auto relative">
      {/* === Title section === */}
      <div className="mt-[120px] text-center animate-fade-in-up">
        <h1
          className="text-glow mb-4"
          style={{
            fontSize: "clamp(40px, 5vw, 56px)",
            fontWeight: 800,
            fontFamily: "var(--font-display)",
            color: "var(--text-primary)",
            lineHeight: 1.2,
          }}
        >
          有什么新想法吗？
        </h1>
        <p style={{ fontSize: "16px", fontFamily: "var(--font-body)", color: "var(--text-secondary)" }}>
          选择一个智能助手，开始聊天
        </p>
      </div>

      {/* === Model selector + Input === */}
      <div className="w-full max-w-[800px] px-6 mt-[48px] space-y-[32px] animate-fade-in-scale">
        {/* Model selector */}
        {agents.length > 0 && (
          <div
            className="flex items-center px-4"
            style={{
              height: "56px",
              background: "var(--glass-bg)",
              backdropFilter: "blur(var(--glass-blur))",
              WebkitBackdropFilter: "blur(var(--glass-blur))",
              border: "2px solid rgba(99, 102, 241, 0.4)",
              borderRadius: "12px",
              boxShadow: "var(--neon-glow)",
            }}
          >
            <Select
              value={effectiveAgentId}
              onChange={(value) => setSelectedAgentId(value)}
              style={{ width: "100%" }}
              variant="borderless"
              suffixIcon={<DownOutlined style={{ color: "var(--text-secondary)", fontSize: 12 }} />}
              placeholder="选择智能助手"
              optionRender={(option) => (
                <div className="flex items-center gap-2">
                  <span className="text-base">{agentsWithEmoji.find((a) => a.id === option.value)?.emoji}</span>
                  <span style={{ fontFamily: "var(--font-body)", fontSize: 14 }}>{option.label}</span>
                </div>
              )}
              options={agentsWithEmoji.map((agent) => ({
                value: agent.id,
                label: agent.name,
              }))}
            />
          </div>
        )}

        {/* Input bar */}
        <div
          className="flex items-center px-5"
          style={{
            height: "56px",
            background: "var(--glass-bg)",
            backdropFilter: "blur(var(--glass-blur))",
            WebkitBackdropFilter: "blur(var(--glass-blur))",
            border: "2px solid rgba(99, 102, 241, 0.5)",
            borderRadius: "20px",
            boxShadow: "var(--neon-glow)",
            transition: "all 0.3s ease-out",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.8)";
            e.currentTarget.style.boxShadow = "0 0 25px rgba(99, 102, 241, 0.5)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.5)";
            e.currentTarget.style.boxShadow = "var(--neon-glow)";
          }}
        >
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
            placeholder="输入消息开始对话..."
            className="flex-1 bg-transparent border-none outline-none"
            style={{
              fontSize: "16px",
              fontFamily: "var(--font-body)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !message.trim()}
            className="flex items-center justify-center shrink-0 transition-all duration-150"
            style={{
              width: "40px",
              height: "40px",
              background: message.trim() ? "var(--color-primary)" : "rgba(99, 102, 241, 0.3)",
              borderRadius: "8px",
              border: "none",
              cursor: message.trim() ? "pointer" : "default",
              opacity: message.trim() ? 1 : 0.5,
            }}
            onMouseEnter={(e) => {
              if (message.trim()) {
                e.currentTarget.style.opacity = "0.9";
                e.currentTarget.style.boxShadow = "0 0 15px rgba(99, 102, 241, 0.4)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "1";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <SendOutlined style={{ color: "#f0f4ff", fontSize: 16 }} />
          </button>
        </div>

        {/* Suggestion cards */}
        <div className="mt-[32px]">
          <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "12px", fontFamily: "var(--font-body)" }}>
            或者尝试以下建议：
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestions.map((s, i) => (
              <div
                key={i}
                onClick={() => { setMessage(s.text); }}
                className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-all duration-300"
                style={{
                  background: "var(--glass-bg-light)",
                  backdropFilter: "blur(8px)",
                  WebkitBackdropFilter: "blur(8px)",
                  border: "1px solid rgba(165, 180, 252, 0.15)",
                  borderRadius: "12px",
                  minHeight: "60px",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(26, 26, 46, 0.7)";
                  e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.5)";
                  e.currentTarget.style.boxShadow = "var(--neon-glow)";
                  e.currentTarget.style.color = "var(--color-accent)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--glass-bg-light)";
                  e.currentTarget.style.borderColor = "rgba(165, 180, 252, 0.15)";
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                <span className="text-xl shrink-0">{s.icon}</span>
                <span style={{ fontSize: "14px", fontFamily: "var(--font-body)", color: "var(--text-primary)" }}>
                  {s.text}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-auto pb-6 pt-12 text-center" style={{ color: "var(--text-secondary)", fontSize: "12px", fontFamily: "var(--font-body)" }}>
        由 Anime Agent 驱动 | 梦幻赛博朋克美学
      </div>
    </div>
  );
}