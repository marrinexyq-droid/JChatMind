package com.kama.jchatmind.agent;

import com.kama.jchatmind.converter.ChatMessageConverter;
import com.kama.jchatmind.message.SseMessage;
import com.kama.jchatmind.model.dto.ChatMessageDTO;
import com.kama.jchatmind.model.dto.KnowledgeBaseDTO;
import com.kama.jchatmind.model.request.UpdateChatMessageRequest;
import com.kama.jchatmind.model.response.CreateChatMessageResponse;
import com.kama.jchatmind.model.vo.ChatMessageVO;
import com.kama.jchatmind.model.vo.RagTrace;
import com.kama.jchatmind.service.ChatMessageFacadeService;
import com.kama.jchatmind.service.RagTraceContext;
import com.kama.jchatmind.service.SseService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.messages.*;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.DefaultToolCallingChatOptions;
import org.springframework.ai.model.tool.ToolCallingManager;
import org.springframework.ai.model.tool.ToolExecutionResult;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.util.Assert;
import org.springframework.util.StringUtils;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

@Slf4j
public class JChatMind {
    // 智能体 ID
    private String agentId;

    // 名称
    private String name;

    // 描述
    private String description;

    // 默认系统提示词
    private String systemPrompt;

    // 交互实例
    private ChatClient chatClient;

    // 状态
    private AgentState agentState;

    // 可用的工具
    private List<ToolCallback> availableTools;

    // 可访问的知识库
    private List<KnowledgeBaseDTO> availableKbs;

    // 工具调用管理器
    private ToolCallingManager toolCallingManager;

    // 模型的聊天记录
    private ChatMemory chatMemory;

    // 模型的聊天会话 ID
    private String chatSessionId;

    // 最多循环次数
    private static final Integer MAX_STEPS = 20;

    private static final Integer DEFAULT_MAX_MESSAGES = 20;

    // 工具返回结果存入 chatMemory 时的最大字符数，避免大量文本干扰 LLM 决策
    private static final int MAX_TOOL_RESPONSE_LENGTH = 2000;

    // SpringAI 自带的 ChatOptions, 不是 AgentDTO.ChatOptions
    private ChatOptions chatOptions;

    // SSE 服务, 用于发送消息给前端
    private SseService sseService;

    private ChatMessageConverter chatMessageConverter;

    private ChatMessageFacadeService chatMessageFacadeService;

    // 最后一次的 ChatResponse
    private ChatResponse lastChatResponse;

    private RagTrace lastRagTrace;

    // AI 返回的，已经持久化，但是需要 sse 发给前端的消息
    private final List<ChatMessageDTO> pendingChatMessages = new ArrayList<>();

    public JChatMind() {
    }

    public JChatMind(String agentId,
                     String name,
                     String description,
                     String systemPrompt,
                     ChatClient chatClient,
                     Integer maxMessages,
                     List<Message> memory,
                     List<ToolCallback> availableTools,
                     List<KnowledgeBaseDTO> availableKbs,
                     String chatSessionId,
                     SseService sseService,
                     ChatMessageFacadeService chatMessageFacadeService,
                     ChatMessageConverter chatMessageConverter
    ) {
        this.agentId = agentId;
        this.name = name;
        this.description = description;
        this.systemPrompt = systemPrompt;

        this.chatClient = chatClient;

        this.availableTools = availableTools;
        this.availableKbs = availableKbs;

        this.chatSessionId = chatSessionId;
        this.sseService = sseService;

        this.chatMessageFacadeService = chatMessageFacadeService;
        this.chatMessageConverter = chatMessageConverter;

        this.agentState = AgentState.IDLE;

        // 保存聊天记录
        this.chatMemory = MessageWindowChatMemory.builder()
                .maxMessages(maxMessages == null ? DEFAULT_MAX_MESSAGES : maxMessages)
                .build();
        this.chatMemory.add(chatSessionId, memory);

        // 关闭 SpringAI 自带的内部的工具调用自动执行功能
        this.chatOptions = DefaultToolCallingChatOptions.builder()
                .internalToolExecutionEnabled(false)
                .build();

        // 工具调用管理器
        this.toolCallingManager = ToolCallingManager.builder().build();
    }

    // 打印工具调用信息
    private void logToolCalls(List<AssistantMessage.ToolCall> toolCalls) {
        if (toolCalls == null || toolCalls.isEmpty()) {
            log.info("\n\n[ToolCalling] 无工具调用");
            return;
        }
        String logMessage = IntStream.range(0, toolCalls.size())
                .mapToObj(i -> {
                    AssistantMessage.ToolCall call = toolCalls.get(i);
                    return String.format(
                            "[ToolCalling #%d]\n- name      : %s\n- arguments : %s",
                            i + 1,
                            call.name(),
                            call.arguments()
                    );
                })
                .collect(Collectors.joining("\n\n"));
        log.info("\n\n========== Tool Calling ==========\n{}\n=================================\n", logMessage);
    }

    // 持久化 Message, 返回 chatMessageId
    // 需要 Agent 持久化的 Message 子类有以下两类
    // AssistantMessage
    // ToolResponseMessage

    // SystemMessage 不需要持久化
    // UserMessage 在每次用户发送问题之间就已经持久化过了
    private void saveMessage(Message message) {
        ChatMessageDTO.ChatMessageDTOBuilder builder = ChatMessageDTO.builder();
        if (message instanceof AssistantMessage assistantMessage) {
            ChatMessageDTO chatMessageDTO = builder.role(ChatMessageDTO.RoleType.ASSISTANT)
                    .content(assistantMessage.getText())
                    .sessionId(this.chatSessionId)
                    .metadata(ChatMessageDTO.MetaData.builder()
                            .toolCalls(assistantMessage.getToolCalls())
                            .ragTrace(this.lastRagTrace)
                            .build())
                    .build();
            CreateChatMessageResponse chatMessage = chatMessageFacadeService.createChatMessage(chatMessageDTO);
            chatMessageDTO.setId(chatMessage.getChatMessageId());
            pendingChatMessages.add(chatMessageDTO);
        } else if (message instanceof ToolResponseMessage toolResponseMessage) {
            // 持久化 ToolResponseMessage
            for (ToolResponseMessage.ToolResponse toolResponse : toolResponseMessage.getResponses()) {
                RagTrace ragTrace = "KnowledgeTool".equals(toolResponse.name()) ? RagTraceContext.consume() : null;
                if (ragTrace != null) {
                    this.lastRagTrace = ragTrace;
                }
                ChatMessageDTO chatMessageDTO = builder.role(ChatMessageDTO.RoleType.TOOL)
                        .content(toolResponse.responseData())
                        .sessionId(this.chatSessionId)
                        .metadata(ChatMessageDTO.MetaData.builder()
                                .toolResponse(toolResponse)
                                .ragTrace(ragTrace)
                                .build())
                        .build();
                CreateChatMessageResponse chatMessage = chatMessageFacadeService.createChatMessage(chatMessageDTO);
                chatMessageDTO.setId(chatMessage.getChatMessageId());
                pendingChatMessages.add(chatMessageDTO);
            }
        } else {
            throw new IllegalArgumentException("不支持的 Message 类型: " + message.getClass().getName());
        }
    }

    // 刷新 pendingMessages, 将数据通过 sse 发送给前端
    private void refreshPendingMessages() {
        for (ChatMessageDTO message : pendingChatMessages) {
            ChatMessageVO vo = chatMessageConverter.toVO(message);
            SseMessage sseMessage = SseMessage.builder()
                    .type(SseMessage.Type.AI_GENERATED_CONTENT)
                    .payload(SseMessage.Payload.builder()
                            .message(vo)
                            .build())
                    .metadata(SseMessage.Metadata.builder()
                            .chatMessageId(message.getId())
                            .build())
                    .build();
            sseService.send(this.chatSessionId, sseMessage);
        }
        pendingChatMessages.clear();
    }

    private boolean think() {
        String thinkToolRules = """
                判断意图并选择工具：
                - 用户问天气 → 调用 queryWeather（参数 city 为城市名，没说城市就问）
                - 用户查知识库/文档 → 调用 KnowledgeTool
                - 调用 KnowledgeTool 时传入 kbsId、query；如果是“它/这个/上述/继续/再详细说”等多轮追问，把上一轮明确主题放入 context
                - 其他 → 直接回答

                【重要规则】
                如果工具结果已存在于对话中，直接用结果回答，不要再调工具

                知识库：%s
                """.formatted(this.availableKbs)
                + "\nIf KnowledgeTool returns chunks marked [C1], [C2], etc., cite the relevant marker at the end of each sentence that uses that chunk.\n";

        String thinkPrompt = StringUtils.hasLength(this.systemPrompt)
                ? this.systemPrompt + "\n\n---\n\n" + thinkToolRules
                : thinkToolRules;

        // 使用 chatMemory 中的全部消息，让 LLM 能关联多轮对话上下文
        // execute() 中已通过 clear+add 原子替换管理 agent loop 内的消息生命周期
        List<Message> thinkMessages = this.chatMemory.get(this.chatSessionId);
        if (thinkMessages == null || thinkMessages.isEmpty()) {
            thinkMessages = List.of();
        }

        Prompt prompt = Prompt.builder()
                .chatOptions(this.chatOptions)
                .messages(thinkMessages)
                .build();

        // 预建空消息，获取 chatMessageId 用于流式追加
        // 注意：使用 createChatMessage(ChatMessageDTO) 而非 (CreateChatMessageRequest)，不触发 ChatEvent。
        // 流式模式下实时内容通过 SSE 推送，不需要 ChatEvent 驱动前端渲染。
        ChatMessageDTO preMsg = ChatMessageDTO.builder()
                .role(ChatMessageDTO.RoleType.ASSISTANT)
                .content("")
                .sessionId(this.chatSessionId)
                .metadata(ChatMessageDTO.MetaData.builder()
                        .toolCalls(List.of())
                        .ragTrace(this.lastRagTrace)
                        .build())
                .build();
        String chatMessageId = chatMessageFacadeService.createChatMessage(preMsg)
                .getChatMessageId();

        // 流式调用 LLM：缓冲 chunks，流结束后一次性持久化，减少 DB 写入次数
        List<String> chunks = new ArrayList<>();

        Flux<ChatResponse> flux = this.chatClient
                .prompt(prompt)
                .system(thinkPrompt)
                .toolCallbacks(this.availableTools.toArray(new ToolCallback[0]))
                .stream()
                .chatResponse();

        try {
            this.lastChatResponse = flux
                    .doOnNext(response -> {
                        String delta = response.getResult().getOutput().getText();
                        if (delta != null && !delta.isEmpty()) {
                            chunks.add(delta);
                            streamChunk(chatMessageId, delta, false);
                        }
                    })
                    .doOnComplete(() -> streamChunk(chatMessageId, "", true))
                    .blockLast();
        } catch (Exception e) {
            // 流式异常时清理已创建的空消息，避免留下孤儿记录
            log.error("流式调用失败，清理预创建消息: chatMessageId={}", chatMessageId, e);
            try {
                chatMessageFacadeService.deleteChatMessage(chatMessageId);
            } catch (Exception ignored) {
            }
            return false;
        }

        Assert.notNull(lastChatResponse, "Last chat client response cannot be null");

        // 流结束后一次性持久化完整内容
        if (!chunks.isEmpty()) {
            chatMessageFacadeService.appendChatMessage(chatMessageId, String.join("", chunks));
        }

        var result = this.lastChatResponse.getResult();
        Assert.notNull(result, "Chat response result cannot be null");
        AssistantMessage output = result.getOutput();

        List<AssistantMessage.ToolCall> toolCalls = output.getToolCalls();
        if (toolCalls == null) {
            toolCalls = List.of();
        }

        // 流完成后更新消息 metadata（工具调用信息），并通过 SSE 通知前端
        if (!toolCalls.isEmpty()) {
            UpdateChatMessageRequest updateReq = new UpdateChatMessageRequest();
            updateReq.setMetadata(ChatMessageDTO.MetaData.builder()
                    .toolCalls(toolCalls)
                    .build());
            chatMessageFacadeService.updateChatMessage(chatMessageId, updateReq);

            // 发送 SSE 事件通知前端消息已更新（含工具调用信息）
            SseMessage metaUpdateMsg = SseMessage.builder()
                    .type(SseMessage.Type.AI_GENERATED_CONTENT)
                    .payload(SseMessage.Payload.builder()
                            .message(ChatMessageVO.builder()
                                    .id(chatMessageId)
                                    .sessionId(this.chatSessionId)
                                    .role(ChatMessageDTO.RoleType.ASSISTANT)
                                    .content(output.getText())
                                    .metadata(ChatMessageDTO.MetaData.builder()
                                            .toolCalls(toolCalls)
                                            .ragTrace(this.lastRagTrace)
                                            .build())
                                    .build())
                            .build())
                    .metadata(SseMessage.Metadata.builder()
                            .chatMessageId(chatMessageId)
                            .build())
                    .build();
            sseService.send(this.chatSessionId, metaUpdateMsg);
        }

        logToolCalls(toolCalls);

        return !toolCalls.isEmpty();
    }

    private void streamChunk(String chatMessageId, String content, boolean done) {
        ChatMessageVO vo = ChatMessageVO.builder()
                .id(chatMessageId)
                .sessionId(this.chatSessionId)
                .role(ChatMessageDTO.RoleType.ASSISTANT)
                .content(content)
                .metadata(done && this.lastRagTrace != null
                        ? ChatMessageDTO.MetaData.builder()
                        .ragTrace(this.lastRagTrace)
                        .build()
                        : null)
                .build();
        SseMessage sseMsg = SseMessage.builder()
                .type(SseMessage.Type.AI_STREAMING_CHUNK)
                .payload(SseMessage.Payload.builder()
                        .message(vo)
                        .done(done)
                        .build())
                .metadata(SseMessage.Metadata.builder()
                        .chatMessageId(chatMessageId)
                        .build())
                .build();
        sseService.send(this.chatSessionId, sseMsg);
    }

    // 执行
    private void execute() {
        Assert.notNull(this.lastChatResponse, "Last chat client response cannot be null");

        if (!this.lastChatResponse.hasToolCalls()) {
            return;
        }

        Prompt prompt = Prompt.builder()
                .messages(this.chatMemory.get(this.chatSessionId))
                .chatOptions(this.chatOptions)
                .build();

        ToolExecutionResult toolExecutionResult = toolCallingManager.executeToolCalls(prompt, this.lastChatResponse);

        List<Message> conversationHistory = toolExecutionResult.conversationHistory();
        if (conversationHistory == null || conversationHistory.isEmpty()) {
            log.warn("conversationHistory 为空，跳过 execute");
            return;
        }
        Message lastMsg = conversationHistory.get(conversationHistory.size() - 1);
        if (!(lastMsg instanceof ToolResponseMessage toolResponseMessage)) {
            log.warn("最后一条消息不是 ToolResponseMessage，跳过 execute");
            return;
        }

        // 截断工具返回结果，避免大量文本干扰 LLM 后续决策
        List<ToolResponseMessage.ToolResponse> truncatedResponses = toolResponseMessage.getResponses().stream()
                .map(resp -> {
                    String data = resp.responseData();
                    if (data != null && data.length() > MAX_TOOL_RESPONSE_LENGTH) {
                        data = data.substring(0, MAX_TOOL_RESPONSE_LENGTH) + "...(内容过长已截断)";
                    }
                    return new ToolResponseMessage.ToolResponse(resp.id(), resp.name(), data);
                })
                .toList();
        List<Message> truncatedHistory = new ArrayList<>(conversationHistory);
        truncatedHistory.set(truncatedHistory.size() - 1,
                ToolResponseMessage.builder()
                        .responses(truncatedResponses)
                        .build());

        this.chatMemory.clear(this.chatSessionId);
        this.chatMemory.add(this.chatSessionId, truncatedHistory);

        String collect = toolResponseMessage.getResponses()
                .stream()
                .map(resp -> "工具" + resp.name() + "的返回结果为：" + resp.responseData())
                .collect(Collectors.joining("\n"));

        log.info("工具调用结果：{}", collect);

        saveMessage(toolResponseMessage);
        refreshPendingMessages();

        if (toolResponseMessage.getResponses()
                .stream()
                .anyMatch(resp -> resp.name().equals("terminate"))) {
            this.agentState = AgentState.FINISHED;
            log.info("任务结束");
        }
    }

    // 单个步骤模板
    private void step() {
        if (think()) {
            execute();
        } else { // 没有工具调用
            agentState = AgentState.FINISHED;
            // 确保 pending 消息在结束前全部发送给前端
            refreshPendingMessages();
        }
    }

    // 运行
    public void run() {
        if (agentState != AgentState.IDLE) {
            throw new IllegalStateException("Agent is not idle");
        }

        try {
            for (int i = 0; i < MAX_STEPS && agentState != AgentState.FINISHED; i++) {
                // 当前步骤，用于实现 Agent Loop
                int currentStep = i + 1;
                step();
                if (currentStep >= MAX_STEPS) {
                    agentState = AgentState.FINISHED;
                    log.warn("Max steps reached, stopping agent");
                }
            }
            agentState = AgentState.FINISHED;
        } catch (Exception e) {
            agentState = AgentState.ERROR;
            log.error("Error running agent", e);
            throw new RuntimeException("Error running agent", e);
        }
    }

    @Override
    public String toString() {
        return "JChatMind {" +
                "name = " + name + ",\n" +
                "description = " + description + ",\n" +
                "agentId = " + agentId + ",\n" +
                "systemPrompt = " + systemPrompt + "}";
    }
}
