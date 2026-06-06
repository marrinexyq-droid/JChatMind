import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { message as antdMessage } from "antd";
import AgentChatHistory from "./agentChatView/AgentChatHistory.tsx";
import AgentChatInput from "./agentChatView/AgentChatInput.tsx";
import {
  createChatMessage,
  createChatSession,
  getChatMessagesBySessionId,
  getChatSession,
} from "../../api/api.ts";
import { BASE_URL } from "../../api/http.ts";
import { useAgents } from "../../hooks/useAgents.tsx";
import { useChatSessions } from "../../hooks/useChatSessions.ts";
import { useUniversePipeline } from "../../contexts/UniversePipelineContext.tsx";
import EmptyAgentChatView from "./agentChatView/EmptyAgentChatView.tsx";
import type { ChatMessageVO, SseMessage, SseMessageType } from "../../types";

export default function AgentChatView() {
  const { chatSessionId } = useParams<{ chatSessionId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { agents } = useAgents();
  const { refreshChatSessions } = useChatSessions();
  const { publishUserMessage, publishSseMessage, publishError } = useUniversePipeline();
  const [messages, setMessages] = useState<ChatMessageVO[]>([]);
  const [feedbackMap, setFeedbackMap] = useState<Record<string, "like" | "dislike" | null>>({});
  const [agentId, setAgentId] = useState("");

  const handleFeedback = (messageId: string, type: "like" | "dislike") => {
    setFeedbackMap((prev) => ({ ...prev, [messageId]: prev[messageId] === type ? null : type }));
  };

  const handleRegenerate = async (messageId: string) => {
    if (!chatSessionId) return;
    // Find the last user message before the clocked assistant message
    const idx = messages.findIndex((m) => m.id === messageId);
    const prevUserMsg = messages.slice(0, idx).reverse().find((m) => m.role === "user");
    const content = prevUserMsg?.content || "";
    if (!content) return;

    handleSendMessage(content);
  };

  const upsertMessage = (message: ChatMessageVO) =>
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === message.id);
      if (idx >= 0) {
        const updated = [...prev];
        const incomingContent = message.content || "";
        const nextContent = incomingContent && !updated[idx].content.endsWith(incomingContent)
          ? updated[idx].content + incomingContent
          : updated[idx].content;
        updated[idx] = {
          ...updated[idx],
          content: nextContent,
          metadata: message.metadata || updated[idx].metadata,
        };
        return updated;
      }
      return [...prev, message];
    });

  const getChatMessages = useCallback(async () => {
    if (!chatSessionId) return;
    const resp = await getChatMessagesBySessionId(chatSessionId);
    setMessages(resp.chatMessages);
    getChatSession(chatSessionId).then((resp) => setAgentId(resp.chatSession.agentId));
  }, [chatSessionId]);

  useEffect(() => {
    if (!chatSessionId) return;
    getChatMessages();
  }, [chatSessionId, getChatMessages]);

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;
    window.petActions?.setThink?.();
    publishUserMessage(chatSessionId, message);

    if (!chatSessionId) {
      if (!agentId) {
        antdMessage.warning("请先创建一个智能体助手");
        return;
      }
      setLoading(true);
      try {
        const response = await createChatSession({ agentId, title: message.slice(0, 20) });
        await createChatMessage({
          agentId,
          sessionId: response.chatSessionId,
          role: "user",
          content: message,
        });
        await refreshChatSessions();
        navigate(`/chat/${response.chatSessionId}`, { replace: true });
      } catch (error) {
        console.error("创建聊天会话失败:", error);
        antdMessage.error("创建聊天会话失败，请重试");
      } finally {
        setLoading(false);
      }
    } else {
      // Add user message locally, let SSE push AI response
      const tempId = `user-${Date.now()}`;
      upsertMessage({
        id: tempId,
        sessionId: chatSessionId,
        role: "user",
        content: message,
      });
      await createChatMessage({
        agentId: agentId || "",
        sessionId: chatSessionId,
        role: "user",
        content: message,
      });
      // No getChatMessages() — avoids overwriting SSE-streamed AI response
    }
  };

  const [displayAgentStatus, setDisplayAgentStatus] = useState(false);
  const [agentStatusText, setAgentStatusText] = useState("");
  const [agentStatusType, setAgentStatusType] = useState<SseMessageType | undefined>();

  useEffect(() => {
    if (!chatSessionId) return;
    const baseRoot = BASE_URL.replace("/api", "");
    const es = new EventSource(`${baseRoot}/sse/connect/${chatSessionId}`);

    es.onerror = (error) => console.error("SSE error:", error);

    es.addEventListener("message", (event) => {
      let msg: SseMessage;
      try {
        msg = JSON.parse(event.data) as SseMessage;
      } catch (error) {
        console.error("SSE parse error:", error);
        publishError(chatSessionId, "Could not parse pipeline event");
        return;
      }
      publishSseMessage(chatSessionId, msg);
      if (msg.type === "AI_GENERATED_CONTENT") {
        if (msg.payload.message) upsertMessage(msg.payload.message);
      } else if (msg.type === "AI_STREAMING_CHUNK") {
        if (msg.payload.message) upsertMessage(msg.payload.message);
        if (msg.payload.done) {
          window.petActions?.setExcite?.();
        }
      } else if (msg.type === "AI_PLANNING") {
        setDisplayAgentStatus(true);
        setAgentStatusText(msg.payload.statusText ?? "");
        setAgentStatusType("AI_PLANNING");
      } else if (msg.type === "AI_THINKING") {
        setDisplayAgentStatus(true);
        setAgentStatusText(msg.payload.statusText ?? "");
        setAgentStatusType("AI_THINKING");
      } else if (msg.type === "AI_EXECUTING") {
        setDisplayAgentStatus(true);
        setAgentStatusText(msg.payload.statusText ?? "");
        setAgentStatusType("AI_EXECUTING");
      } else if (msg.type === "AI_DONE") {
        setDisplayAgentStatus(false);
        setAgentStatusText("");
        setAgentStatusType(undefined);
        window.petActions?.setExcite?.();
      } else {
        throw new Error(`Unknown message type: ${msg.type}`);
      }
    });

    es.addEventListener("init", (event) => {
      console.log("Received init message:", event.data);
    });

    return () => {
      es.close();
    };
  }, [chatSessionId, publishError, publishSseMessage]);

  if (!chatSessionId) {
    return <EmptyAgentChatView agents={agents} loading={loading} />;
  }

  return (
    <div className="flex flex-col h-full">
      <AgentChatHistory
        messages={messages}
        displayAgentStatus={displayAgentStatus}
        agentStatusText={agentStatusText}
        agentStatusType={agentStatusType}
        feedbackMap={feedbackMap}
        onFeedback={handleFeedback}
        onRegenerate={handleRegenerate}
      />
      <div className="absolute bottom-6 left-6 right-6 z-10 max-w-3xl mx-auto">
        <AgentChatInput onSend={handleSendMessage} />
      </div>
    </div>
  );
}
