import { useNavigate, useLocation } from "react-router-dom";
import { PlusOutlined, RobotOutlined, BookOutlined, CompassOutlined } from "@ant-design/icons";
import ChatTabContent from "./tabs/ChatTabContent.tsx";

interface SideMenuProps {
  onCreateAgentClick: () => void;
  onCreateKnowledgeBaseClick: () => void;
}

export default function SideMenu({
  onCreateAgentClick,
  onCreateKnowledgeBaseClick,
}: SideMenuProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex flex-col h-full">
      {/* New chat button */}
      <div className="px-4 pt-3 pb-2">
        <button
          onClick={() => {
            window.petActions?.setCurious?.();
            navigate("/chat");
          }}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-colors text-sm font-medium"
          style={{
            background: "rgba(255,255,255,0.04)",
            color: "var(--text-primary)",
            border: "1px solid var(--glass-border)",
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
        >
          <PlusOutlined className="text-base" />
          <span>新对话</span>
        </button>
      </div>

      {/* Recent chats */}
      <div className="flex-1 min-h-0 overflow-y-auto px-2">
        <ChatTabContent />
      </div>

      {/* Bottom nav */}
      <div className="px-3 py-3 border-t" style={{ borderColor: "var(--glass-border)" }}>
        <div className="flex items-center justify-between px-3 py-2.5 rounded-lg text-sm"
          style={{ color: "var(--text-muted)" }}>
          <span className="text-xs font-semibold uppercase tracking-wider">管理</span>
        </div>

        {/* Agent nav + create button */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              window.petActions?.setCurious?.();
              navigate("/agent");
            }}
            className="flex-1 flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm"
            style={{
              color: location.pathname.startsWith("/agent") ? "var(--text-primary)" : "var(--text-secondary)",
              background: location.pathname.startsWith("/agent") ? "rgba(255,255,255,0.06)" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!location.pathname.startsWith("/agent"))
                e.currentTarget.style.background = "rgba(255,255,255,0.04)";
            }}
            onMouseLeave={(e) => {
              if (!location.pathname.startsWith("/agent"))
                e.currentTarget.style.background = "transparent";
            }}
          >
            <span className="text-base"><RobotOutlined /></span>
            <span>智能体管理</span>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onCreateAgentClick(); }}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors shrink-0"
            title="新建智能体"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            <PlusOutlined className="text-xs" />
          </button>
        </div>

        {/* KB nav + create button */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              window.petActions?.setCurious?.();
              navigate("/knowledge-base");
            }}
            className="flex-1 flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm"
            style={{
              color: location.pathname.startsWith("/knowledge-base") ? "var(--text-primary)" : "var(--text-secondary)",
              background: location.pathname.startsWith("/knowledge-base") ? "rgba(255,255,255,0.06)" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!location.pathname.startsWith("/knowledge-base"))
                e.currentTarget.style.background = "rgba(255,255,255,0.04)";
            }}
            onMouseLeave={(e) => {
              if (!location.pathname.startsWith("/knowledge-base"))
                e.currentTarget.style.background = "transparent";
            }}
          >
            <span className="text-base"><BookOutlined /></span>
            <span>知识库</span>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onCreateKnowledgeBaseClick(); }}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors shrink-0"
            title="新建知识库"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            <PlusOutlined className="text-xs" />
          </button>
        </div>

        {/* Planetarium nav */}
        <button
          onClick={() => {
            window.petActions?.setCurious?.();
            navigate("/planetarium");
          }}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm mt-1"
          style={{
            color: location.pathname === "/planetarium" ? "var(--text-primary)" : "var(--text-secondary)",
            background: location.pathname === "/planetarium" ? "rgba(255,255,255,0.06)" : "transparent",
          }}
          onMouseEnter={(e) => {
            if (location.pathname !== "/planetarium")
              e.currentTarget.style.background = "rgba(255,255,255,0.04)";
          }}
          onMouseLeave={(e) => {
            if (location.pathname !== "/planetarium")
              e.currentTarget.style.background = "transparent";
          }}
        >
          <span className="text-base"><CompassOutlined /></span>
          <span>赛博行星仪</span>
        </button>
      </div>
    </div>
  );
}
