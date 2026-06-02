import { useState, useRef, useEffect, useCallback } from "react";
import { Bubble } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import {
  ToolOutlined,
  CheckCircleOutlined,
  RobotOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import type { ChatMessageVO, SseMessageType, ToolCall, ToolResponse } from "../../../types";
import MessageActions from "./MessageActions";

interface AgentChatHistoryProps {
  messages: ChatMessageVO[];
  displayAgentStatus?: boolean;
  agentStatusText?: string;
  agentStatusType?: SseMessageType;
  feedbackMap?: Record<string, "like" | "dislike" | null>;
  onFeedback?: (messageId: string, type: "like" | "dislike") => void;
  onRegenerate?: (messageId: string) => void;
}

const CollapsibleToolCalls: React.FC<{ toolCalls: ToolCall[] }> = ({ toolCalls }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-colors"
        style={{
          background: "rgba(139, 156, 247, 0.06)",
          border: "1px solid rgba(139, 156, 247, 0.12)",
          color: "var(--text-secondary)",
        }}
      >
        {expanded ? <DownOutlined /> : <RightOutlined />}
        <ToolOutlined style={{ color: "var(--accent-blue)" }} />
        <span>已调用 {toolCalls.length} 个工具检索知识库</span>
        <span style={{ color: "var(--text-muted)" }}>
          {expanded ? "点击收起" : "点击展开"}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 ml-4 space-y-1.5">
          {toolCalls.map((tc) => {
            let parsedArgs: Record<string, unknown> = {};
            try { parsedArgs = JSON.parse(tc.arguments) as Record<string, unknown>; } catch { /* ignore */ }
            return (
              <div key={tc.id} className="text-xs flex items-center gap-1.5 py-0.5">
                <span className="font-mono" style={{ color: "var(--accent-blue)" }}>{tc.name}</span>
                {Object.keys(parsedArgs).length > 0 && (
                  <>
                    <span style={{ color: "var(--text-muted)" }}>·</span>
                    <span className="truncate max-w-[300px]" style={{ color: "var(--text-secondary)" }}>
                      {Object.entries(parsedArgs).slice(0, 3).map(([k, v]) => `${k}=${String(v).slice(0, 40)}`).join(", ")}
                    </span>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ToolResponseDisplay: React.FC<{ toolResponse: ToolResponse }> = ({ toolResponse }) => {
  const [expanded, setExpanded] = useState(false);

  let parsedData: unknown = null;
  let isJson = false;
  let dataPreview = "";

  try {
    parsedData = JSON.parse(toolResponse.responseData);
    isJson = true;
    const jsonStr = JSON.stringify(parsedData);
    dataPreview = jsonStr.length > 100 ? jsonStr.slice(0, 100) + "..." : jsonStr;
  } catch {
    dataPreview = toolResponse.responseData.length > 100
      ? toolResponse.responseData.slice(0, 100) + "..."
      : toolResponse.responseData;
  }

  return (
    <div className="my-1.5 text-xs">
      <div
        className="flex items-center gap-2 cursor-pointer"
        style={{ color: "var(--text-muted)" }}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <DownOutlined style={{ color: "var(--accent-cyan)" }} /> : <RightOutlined style={{ color: "var(--accent-cyan)" }} />}
        <CheckCircleOutlined style={{ color: "var(--color-accent)" }} />
        <span className="font-mono" style={{ color: "var(--color-accent)" }}>{toolResponse.name}</span>
        <span style={{ color: "var(--text-muted)" }}>·</span>
        <span className="truncate flex-1" style={{ color: "var(--text-secondary)" }}>{dataPreview}</span>
      </div>
      {expanded && (
        <div
          className="ml-5 mt-1.5 p-2 rounded-xl"
          style={{ background: "rgba(110, 231, 183, 0.06)", border: "1px solid rgba(110, 231, 183, 0.12)" }}
        >
          <div className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
            {isJson ? (
              <pre className="whitespace-pre-wrap break-words overflow-x-auto max-h-60 overflow-y-auto">
                {JSON.stringify(parsedData, null, 2)}
              </pre>
            ) : (
              <div className="whitespace-pre-wrap break-words">{toolResponse.responseData}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default function AgentChatHistory({
  messages, displayAgentStatus = false, agentStatusText = "",
  agentStatusType, feedbackMap = {}, onFeedback, onRegenerate,
}: AgentChatHistoryProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const SCROLL_THRESHOLD = 20;
  const prevMessagesLengthRef = useRef(messages.length);

  const checkIfNearBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return false;
    const { scrollTop, clientHeight, scrollHeight } = container;
    return scrollHeight - scrollTop - clientHeight <= SCROLL_THRESHOLD;
  }, []);

  const scrollToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    requestAnimationFrame(() => {
      if (container) container.scrollTop = container.scrollHeight;
    });
  }, []);

  const handleScroll = useCallback(() => {
    setIsNearBottom(checkIfNearBottom());
  }, [checkIfNearBottom]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const initTimer = setTimeout(() => setIsNearBottom(checkIfNearBottom()), 0);
    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      clearTimeout(initTimer);
      container.removeEventListener("scroll", handleScroll);
    };
  }, [handleScroll, checkIfNearBottom]);

  useEffect(() => {
    const hasNewMessage = messages.length > prevMessagesLengthRef.current;
    const contentChanged = messages.length === prevMessagesLengthRef.current && messages.length > 0;
    prevMessagesLengthRef.current = messages.length;
    if ((hasNewMessage || contentChanged) && isNearBottom) scrollToBottom();
  }, [messages, isNearBottom, scrollToBottom]);

  useEffect(() => {
    if (displayAgentStatus && isNearBottom) scrollToBottom();
  }, [displayAgentStatus, isNearBottom, scrollToBottom]);

  const getStatusLabel = () => {
    switch (agentStatusType) {
      case "AI_PLANNING": return "规划中";
      case "AI_THINKING": return "思考中";
      case "AI_EXECUTING": return "执行中";
      default: return "处理中";
    }
  };

  return (
    <div ref={scrollContainerRef} className="flex-1 px-4 pt-4 pb-28 overflow-y-auto">
      {messages.map((message) => (
        <div className="mb-6" key={message.id}>
          {message.role === "assistant" && (
            <div className="max-w-3xl">
              {message.metadata?.toolCalls && message.metadata.toolCalls.length > 0 && (
                <CollapsibleToolCalls toolCalls={message.metadata.toolCalls} />
              )}
              {message.content && <div className="x-markdown"><XMarkdown>{message.content}</XMarkdown></div>}
              {onFeedback && onRegenerate && (
                <MessageActions
                  messageId={message.id}
                  content={message.content}
                  feedback={feedbackMap[message.id]}
                  onFeedback={onFeedback}
                  onRegenerate={() => onRegenerate(message.id)}
                />
              )}
            </div>
          )}

          {message.role === "tool" && message.metadata?.toolResponse && (
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                <ToolResponseDisplay toolResponse={message.metadata.toolResponse} />
              </div>
            </div>
          )}

          {message.role === "user" && (
            <div className="flex justify-end">
              <div
                className="max-w-[75%] px-5 py-3 rounded-3xl text-sm leading-relaxed"
                style={{ background: "var(--bg-surface)", color: "var(--text-primary)" }}
              >
                {message.content}
              </div>
            </div>
          )}

          {message.role === "system" && (
            <div className="flex justify-center">
              <div
                className="px-3 py-1 text-xs rounded-full flex items-center gap-1"
                style={{
                  background: "rgba(139, 156, 247, 0.08)",
                  color: "var(--accent-blue)",
                  border: "1px solid rgba(139, 156, 247, 0.12)",
                }}
              >
                <RobotOutlined />
                <span>{message.content}</span>
              </div>
            </div>
          )}
        </div>
      ))}

      {displayAgentStatus && (
        <div className="mb-3">
          <Bubble
            content={
              <span className="flex items-center gap-2 text-sm">
                <span className="font-semibold animate-pulse" style={{ color: "var(--accent-blue)" }}>
                  {getStatusLabel()}
                </span>
                <span style={{ color: "var(--text-muted)" }}>·</span>
                <span style={{ color: "var(--text-secondary)" }}>{agentStatusText}</span>
              </span>
            }
            placement="start"
          />
        </div>
      )}
    </div>
  );
}