import { useNavigate, useLocation } from "react-router-dom";
import {
  MenuUnfoldOutlined,
  PlusOutlined,
  RobotOutlined,
  BookOutlined,
} from "@ant-design/icons";

interface SidebarProps {
  children: React.ReactNode;
  collapsed: boolean;
  onToggle: () => void;
}

function IconButton({ icon, label, active, onClick }: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="w-10 h-10 mx-auto rounded-xl flex items-center justify-center transition-colors"
      style={{
        color: active ? "var(--accent-blue)" : "var(--text-secondary)",
        background: active ? "rgba(139, 156, 247, 0.12)" : "transparent",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "rgba(255,255,255,0.06)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      {icon}
    </button>
  );
}

export default function Sidebar({ children, collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside
      className="h-full flex flex-col shrink-0"
      style={{
        width: collapsed ? "60px" : "264px",
        transition: "width 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
        background: "var(--glass-bg)",
        backdropFilter: "blur(var(--glass-blur))",
        WebkitBackdropFilter: "blur(var(--glass-blur))",
        borderRight: "1px solid rgba(165, 180, 252, 0.15)",
      }}
    >
      {collapsed ? (
        /* --- Minimized Rail --- */
        <div className="h-full flex flex-col items-center py-3 gap-1">
          <IconButton
            icon={<MenuUnfoldOutlined />}
            label="展开侧边栏"
            onClick={onToggle}
          />
          <div className="w-8 h-px my-1" style={{ background: "var(--glass-border)" }} />
          <IconButton
            icon={<PlusOutlined />}
            label="新对话"
            onClick={() => {
              (window as any).petActions?.setCurious?.();
              navigate("/chat");
            }}
          />
          <IconButton
            icon={<RobotOutlined />}
            label="智能体管理"
            active={location.pathname.startsWith("/agent")}
            onClick={() => {
              (window as any).petActions?.setCurious?.();
              navigate("/agent");
            }}
          />
          <IconButton
            icon={<BookOutlined />}
            label="知识库"
            active={location.pathname.startsWith("/knowledge-base")}
            onClick={() => {
              (window as any).petActions?.setCurious?.();
              navigate("/knowledge-base");
            }}
          />
        </div>
      ) : (
        /* --- Expanded Sidebar --- */
        <div style={{ width: "264px", minWidth: "264px" }} className="h-full flex flex-col">
          {children}
        </div>
      )}
    </aside>
  );
}