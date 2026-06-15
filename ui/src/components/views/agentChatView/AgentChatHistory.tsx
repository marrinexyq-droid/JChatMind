import { useState, useRef, useEffect, useCallback } from "react";
import { Bubble } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import {
  ToolOutlined,
  CheckCircleOutlined,
  RobotOutlined,
  DownOutlined,
  RightOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import type { ChatMessageVO, RagTrace, RagTraceChunk, SseMessageType, ToolCall, ToolResponse } from "../../../types";
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

const formatScore = (score?: number) => (typeof score === "number" ? score.toFixed(4) : "-");

const getCitationsFromContent = (content: string) => {
  const matches = content.match(/\[C\d+\]/g) ?? [];
  return Array.from(new Set(matches.map((item) => item.slice(1, -1))));
};

const ChunkCard: React.FC<{ chunk: RagTraceChunk; compact?: boolean }> = ({ chunk, compact = false }) => (
  <div
    className="rounded-lg p-2 text-xs"
    style={{ background: "rgba(255,255,255,0.035)", border: "1px solid rgba(255,255,255,0.08)" }}
  >
    <div className="flex flex-wrap items-center gap-1.5 mb-1">
      {chunk.citationId && (
        <span className="font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(139,156,247,0.14)", color: "var(--accent-blue)" }}>
          {chunk.citationId}
        </span>
      )}
      <span className="font-medium truncate max-w-[260px]" style={{ color: "var(--text-primary)" }}>
        {chunk.documentName || chunk.docId}
      </span>
      {(chunk.matchedBy ?? []).map((source) => (
        <span key={source} className="font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(110,231,183,0.1)", color: "var(--color-accent)" }}>
          {source}
        </span>
      ))}
    </div>
    <div className="flex flex-wrap gap-x-3 gap-y-1 mb-1" style={{ color: "var(--text-muted)" }}>
      {chunk.vectorRank && <span>vector #{chunk.vectorRank} / {formatScore(chunk.vectorScore)}</span>}
      {chunk.bm25Rank && <span>BM25 #{chunk.bm25Rank} / {formatScore(chunk.bm25Score)}</span>}
      {chunk.rrfRank && <span>RRF #{chunk.rrfRank} / {formatScore(chunk.rrfScore)}</span>}
      {chunk.graphRank && <span>graph #{chunk.graphRank} / {formatScore(chunk.graphScore)}</span>}
      {chunk.rerankRank && <span>rerank #{chunk.rerankRank} / {formatScore(chunk.rerankScore)}</span>}
      {chunk.finalRank && <span>final #{chunk.finalRank}</span>}
    </div>
    {!compact && (
      <div className="leading-relaxed line-clamp-3" style={{ color: "var(--text-secondary)" }}>
        {chunk.contentPreview}
      </div>
    )}
  </div>
);

const TraceStage: React.FC<{ title: string; chunks?: RagTraceChunk[]; compact?: boolean }> = ({ title, chunks = [], compact }) => {
  if (!chunks.length) return null;
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
        {title} ({chunks.length})
      </div>
      <div className="space-y-1.5">
        {chunks.slice(0, 8).map((chunk) => (
          <ChunkCard key={`${title}-${chunk.id}-${chunk.finalRank ?? chunk.rrfRank ?? chunk.rerankRank ?? ""}`} chunk={chunk} compact={compact} />
        ))}
      </div>
    </div>
  );
};

const RagTracePanel: React.FC<{ trace: RagTrace; content?: string }> = ({ trace, content = "" }) => {
  const [expanded, setExpanded] = useState(false);
  const cited = getCitationsFromContent(content);
  const citedChunks = (trace.finalChunks ?? []).filter((chunk) => chunk.citationId && cited.includes(chunk.citationId));

  return (
    <div className="mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-colors"
        style={{
          background: "rgba(110, 231, 183, 0.06)",
          border: "1px solid rgba(110, 231, 183, 0.12)",
          color: "var(--text-secondary)",
        }}
      >
        {expanded ? <DownOutlined /> : <RightOutlined />}
        <DatabaseOutlined style={{ color: "var(--color-accent)" }} />
        <span>RAG 证据链</span>
        <span style={{ color: "var(--text-muted)" }}>
          {trace.mode} · final {(trace.finalChunks ?? []).length}
          {trace.rerankFallback ? " · rerank fallback" : ""}
        </span>
      </button>
      {expanded && (
        <div
          className="mt-2 ml-4 p-3 rounded-xl space-y-3"
          style={{ background: "rgba(12, 18, 32, 0.5)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            query: <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{trace.query}</span>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {trace.queryType && <span>type: <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{trace.queryType}</span></span>}
            {trace.plannedQuery && trace.plannedQuery !== trace.query && (
              <span>planned: <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{trace.plannedQuery}</span></span>
            )}
            {trace.candidatePoolSize && <span>pool: {trace.candidatePoolSize}</span>}
            {trace.graphExpansionEnabled && <span>graph: {trace.graphMaxHops ?? 1}-hop</span>}
          </div>
          {trace.selfRagApplied && (
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              Self-RAG:{" "}
              <span className="font-mono" style={{ color: "var(--text-secondary)" }}>
                {trace.selfRagDecision ?? "UNKNOWN"}
              </span>
              <span> · retry {trace.selfRagRetryCount ?? 0}</span>
              {trace.selfRagReason && <span> · {trace.selfRagReason}</span>}
            </div>
          )}
          {citedChunks.length > 0 && <TraceStage title="回答引用" chunks={citedChunks} compact />}
          <div className="grid gap-3 md:grid-cols-2">
            <TraceStage title="向量召回" chunks={trace.vectorResults} compact />
            <TraceStage title="BM25 召回" chunks={trace.bm25Results} compact />
          </div>
          <TraceStage title="RRF 融合后" chunks={trace.rrfResults} compact />
          <TraceStage title="图谱扩展" chunks={trace.graphExpandedChunks} compact />
          <TraceStage title="Rerank 后" chunks={trace.rerankResults} compact />
          <TraceStage title="最终送入 LLM" chunks={trace.finalChunks} />
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
              {message.metadata?.ragTrace && (
                <RagTracePanel trace={message.metadata.ragTrace} content={message.content} />
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
                {message.metadata.ragTrace && (
                  <RagTracePanel trace={message.metadata.ragTrace} content={message.content} />
                )}
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
