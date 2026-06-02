import { Sender } from "@ant-design/x";

interface AgentChatInputProps {
  onSend: (message: string) => void;
}

export default function AgentChatInput({ onSend }: AgentChatInputProps) {
  return (
    <div
      className="rounded-pill px-4 py-3"
      style={{
        background: "var(--glass-bg)",
        backdropFilter: "blur(var(--glass-blur))",
        WebkitBackdropFilter: "blur(var(--glass-blur))",
        border: "2px solid rgba(99, 102, 241, 0.5)",
        boxShadow: "var(--neon-glow)",
      }}
    >
      <Sender
        onSubmit={(value) => {
          const trimmed = value.trim();
          if (trimmed) onSend(trimmed);
        }}
        placeholder="输入消息..."
      />
    </div>
  );
}