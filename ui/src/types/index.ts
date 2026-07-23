export type MessageType = "user" | "assistant" | "system" | "tool";

export interface KnowledgeBase {
  knowledgeBaseId: string;
  name: string;
  description: string;
}

export interface ToolCall {
  id: string;
  type: string;
  name: string;
  arguments: string;
}

export interface ToolResponse {
  id: string;
  name: string;
  responseData: string;
}

export interface RagTraceChunk {
  citationId?: string;
  id: string;
  kbId: string;
  docId: string;
  documentName?: string;
  contentPreview: string;
  metadata?: string;
  matchedBy?: string[];
  vectorRank?: number;
  vectorScore?: number;
  bm25Rank?: number;
  bm25Score?: number;
  rrfRank?: number;
  rrfScore?: number;
  graphRank?: number;
  graphScore?: number;
  rerankRank?: number;
  rerankScore?: number;
  finalRank?: number;
}

export interface RagTrace {
  query: string;
  originalQuery?: string;
  plannedQuery?: string;
  queryType?: string;
  kbId: string;
  mode: string;
  topK: number;
  candidatePoolSize?: number;
  vectorWeight?: number;
  bm25Weight?: number;
  graphExpansionEnabled?: boolean;
  graphMaxHops?: number;
  rerankApplied?: boolean;
  rerankFallback?: boolean;
  selfRagApplied?: boolean;
  selfRagDecision?: string;
  selfRagReason?: string;
  selfRagRetryCount?: number;
  vectorResults?: RagTraceChunk[];
  bm25Results?: RagTraceChunk[];
  rrfResults?: RagTraceChunk[];
  graphExpandedChunks?: RagTraceChunk[];
  rerankResults?: RagTraceChunk[];
  finalChunks?: RagTraceChunk[];
}

export interface ChatMessageVOMetadata {
  toolCalls?: ToolCall[];
  toolResponse?: ToolResponse;
  ragTrace?: RagTrace;
  feedback?: "like" | "dislike" | null;
}

export interface ChatMessageVO {
  id: string;
  sessionId: string;
  role: MessageType;
  content: string;
  metadata?: ChatMessageVOMetadata;
}

export type SseMessageType =
  | "AI_GENERATED_CONTENT"
  | "AI_STREAMING_CHUNK"
  | "AI_PLANNING"
  | "AI_THINKING"
  | "AI_EXECUTING"
  | "AI_DONE";

export interface SseMessagePayload {
  message?: ChatMessageVO;
  statusText?: string;
  done?: boolean;
}

export interface SseMessageMetadata {
  chatMessageId: string;
}

export interface SseMessage {
  type: SseMessageType;
  payload: SseMessagePayload;
  metadata: SseMessageMetadata;
}

export type UniverseReasoningState =
  | "idle"
  | "planning"
  | "thinking"
  | "executing"
  | "streaming"
  | "done"
  | "error";

export interface UniverseTimelineNode {
  id: string;
  type: SseMessageType | "USER_MESSAGE" | "ERROR";
  reasoningState: UniverseReasoningState;
  label: string;
  timestamp: number;
  messageId?: string;
}

export interface UniversePipelineState {
  sessionId?: string;
  lastUserMessage?: string;
  lastAssistantMessageId?: string;
  reasoningState: UniverseReasoningState;
  statusText: string;
  streamTokenEstimate: number;
  toolCallCount: number;
  lastEventAt?: number;
  timeline: UniverseTimelineNode[];
}

declare global {
  interface Window {
    petActions?: {
      setHappy?: () => void;
      setThink?: () => void;
      setCurious?: () => void;
      setExcite?: () => void;
    };
  }
}
