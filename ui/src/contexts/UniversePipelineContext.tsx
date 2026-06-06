/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type {
  SseMessage,
  SseMessageType,
  UniversePipelineState,
  UniverseReasoningState,
  UniverseTimelineNode,
} from "../types";

interface UniversePipelineContextValue {
  state: UniversePipelineState;
  publishUserMessage: (sessionId: string | undefined, content: string) => void;
  publishSseMessage: (sessionId: string | undefined, message: SseMessage) => void;
  publishError: (sessionId: string | undefined, label: string) => void;
  resetUniversePipeline: () => void;
}

const INITIAL_STATE: UniversePipelineState = {
  reasoningState: "idle",
  statusText: "Waiting for the next chat signal",
  streamTokenEstimate: 0,
  toolCallCount: 0,
  timeline: [],
};

const STATE_LABELS: Record<UniverseReasoningState, string> = {
  idle: "Idle orbit",
  planning: "Planning route",
  thinking: "Reasoning active",
  executing: "Executing tools",
  streaming: "Streaming response",
  done: "Pipeline complete",
  error: "Pipeline error",
};

function createTimelineNode(
  type: UniverseTimelineNode["type"],
  reasoningState: UniverseReasoningState,
  label: string,
  messageId?: string,
): UniverseTimelineNode {
  return {
    id: `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    reasoningState,
    label,
    timestamp: Date.now(),
    messageId,
  };
}

function appendTimeline(
  state: UniversePipelineState,
  node: UniverseTimelineNode,
): UniverseTimelineNode[] {
  return [...state.timeline, node].slice(-24);
}

function estimateTokens(text: string | undefined) {
  if (!text) return 0;
  return Math.max(1, Math.ceil(text.trim().length / 4));
}

function getMessageId(message: SseMessage) {
  return message.metadata?.chatMessageId ?? message.payload?.message?.id;
}

function mapSseTypeToState(type: SseMessageType, done?: boolean): UniverseReasoningState {
  if (type === "AI_PLANNING") return "planning";
  if (type === "AI_THINKING") return "thinking";
  if (type === "AI_EXECUTING") return "executing";
  if (type === "AI_STREAMING_CHUNK") return done ? "done" : "streaming";
  if (type === "AI_DONE") return "done";
  return "streaming";
}

const UniversePipelineContext = createContext<UniversePipelineContextValue | undefined>(undefined);

export function UniversePipelineProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<UniversePipelineState>(INITIAL_STATE);

  const publishUserMessage = useCallback((sessionId: string | undefined, content: string) => {
    setState((prev) => {
      const label = content.trim() ? content.trim().slice(0, 80) : "User message";
      const node = createTimelineNode("USER_MESSAGE", "planning", label);
      return {
        ...prev,
        sessionId,
        lastUserMessage: content,
        reasoningState: "planning",
        statusText: "Question captured. Preparing the route.",
        streamTokenEstimate: 0,
        toolCallCount: 0,
        lastEventAt: node.timestamp,
        timeline: appendTimeline(prev, node),
      };
    });
  }, []);

  const publishSseMessage = useCallback((sessionId: string | undefined, message: SseMessage) => {
    setState((prev) => {
      const nextState = mapSseTypeToState(message.type, message.payload?.done);
      const messageId = getMessageId(message);
      const messageText = message.payload?.message?.content ?? "";
      const toolCalls = message.payload?.message?.metadata?.toolCalls?.length ?? 0;
      const toolResponse = message.payload?.message?.metadata?.toolResponse ? 1 : 0;
      const statusText = message.payload?.statusText
        || (message.type === "AI_STREAMING_CHUNK" && !message.payload?.done ? "Response beam is extending." : STATE_LABELS[nextState]);
      const node = createTimelineNode(message.type, nextState, statusText, messageId);

      return {
        ...prev,
        sessionId: sessionId ?? prev.sessionId,
        lastAssistantMessageId: messageId ?? prev.lastAssistantMessageId,
        reasoningState: nextState,
        statusText,
        streamTokenEstimate: message.type === "AI_STREAMING_CHUNK"
          ? prev.streamTokenEstimate + estimateTokens(messageText)
          : prev.streamTokenEstimate,
        toolCallCount: prev.toolCallCount + toolCalls + toolResponse,
        lastEventAt: node.timestamp,
        timeline: appendTimeline(prev, node),
      };
    });
  }, []);

  const publishError = useCallback((sessionId: string | undefined, label: string) => {
    setState((prev) => {
      const node = createTimelineNode("ERROR", "error", label);
      return {
        ...prev,
        sessionId: sessionId ?? prev.sessionId,
        reasoningState: "error",
        statusText: label,
        lastEventAt: node.timestamp,
        timeline: appendTimeline(prev, node),
      };
    });
  }, []);

  const resetUniversePipeline = useCallback(() => setState(INITIAL_STATE), []);

  const value = useMemo(
    () => ({ state, publishUserMessage, publishSseMessage, publishError, resetUniversePipeline }),
    [state, publishUserMessage, publishSseMessage, publishError, resetUniversePipeline],
  );

  return (
    <UniversePipelineContext.Provider value={value}>
      {children}
    </UniversePipelineContext.Provider>
  );
}

export function useUniversePipeline() {
  const context = useContext(UniversePipelineContext);
  if (!context) {
    throw new Error("useUniversePipeline must be used within a UniversePipelineProvider");
  }
  return context;
}
