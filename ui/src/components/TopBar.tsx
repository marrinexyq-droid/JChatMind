import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons";

interface TopBarProps {
  collapsed: boolean;
  onToggle: () => void;
  title?: string;
}

export default function TopBar({ collapsed, onToggle, title }: TopBarProps) {
  return (
    <div className="h-12 flex items-center px-4 gap-3 shrink-0">
      <button
        onClick={onToggle}
        className="w-9 h-9 rounded-xl flex items-center justify-center transition-colors duration-200"
        style={{
          background: "rgba(255,255,255,0.04)",
          color: "var(--text-secondary)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(255,255,255,0.08)";
          e.currentTarget.style.color = "var(--text-primary)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "rgba(255,255,255,0.04)";
          e.currentTarget.style.color = "var(--text-secondary)";
        }}
      >
        {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
      </button>
      {title && (
        <span className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          {title}
        </span>
      )}
    </div>
  );
}