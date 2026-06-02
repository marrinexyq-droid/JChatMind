import { useState } from "react";
import { LikeOutlined, DislikeOutlined, RedoOutlined, CopyOutlined, CheckOutlined } from "@ant-design/icons";

interface MessageActionsProps {
  messageId: string;
  content: string;
  feedback?: "like" | "dislike" | null;
  onFeedback: (messageId: string, type: "like" | "dislike") => void;
  onRegenerate: () => void;
}

export default function MessageActions({
  messageId, content, feedback, onFeedback, onRegenerate,
}: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const btn: React.CSSProperties = {
    background: "none", border: "none", cursor: "pointer",
    padding: "4px 6px", borderRadius: "6px", fontSize: 13,
    display: "inline-flex", alignItems: "center", gap: 4,
    color: "var(--text-muted)", transition: "all 0.15s",
  };

  return (
    <div className="flex items-center gap-1 mt-3 pt-2"
      style={{ borderTop: "1px solid rgba(165,180,252,0.08)" }}>
      <button style={{ ...btn, color: feedback === "like" ? "var(--color-accent)" : "var(--text-muted)" }}
        onClick={() => onFeedback(messageId, "like")} title="赞同"
        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-accent)"; e.currentTarget.style.background = "rgba(6,182,212,0.08)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = feedback === "like" ? "var(--color-accent)" : "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}>
        <LikeOutlined /> 赞同
      </button>
      <button style={{ ...btn, color: feedback === "dislike" ? "#fb7185" : "var(--text-muted)" }}
        onClick={() => onFeedback(messageId, "dislike")} title="反对"
        onMouseEnter={(e) => { e.currentTarget.style.color = "#fb7185"; e.currentTarget.style.background = "rgba(251,113,133,0.08)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = feedback === "dislike" ? "#fb7185" : "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}>
        <DislikeOutlined /> 反对
      </button>
      <button style={btn} onClick={handleCopy} title="复制"
        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}>
        {copied ? <><CheckOutlined style={{ color: "#6ee7b7" }} /> 已复制</> : <><CopyOutlined /> 复制</>}
      </button>
      <button style={btn} onClick={onRegenerate} title="重新生成"
        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}>
        <RedoOutlined /> 重新生成
      </button>
    </div>
  );
}