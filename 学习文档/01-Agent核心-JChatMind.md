# 01 — Agent 核心：JChatMind.java 深度解析

> 文件路径：`jchatmind/src/main/java/com/kama/jchatmind/agent/JChatMind.java`
> 行数：353 行
> 重要性：⭐⭐⭐⭐⭐（整个项目的大脑）

## 一、类的职责

JChatMind 是整个 Agent 系统的核心类，实现了 **Think-Execute 循环**（ReAct 模式）。它的职责是：

1. 接收用户消息的上下文（从 Factory 构建时传入）
2. **Think 阶段**：调 LLM 判断是否要调用工具
3. **Execute 阶段**：如果需要，执行工具调用
4. 循环直到任务完成或达到最大步数
5. 过程中：持久化消息到 DB + 通过 SSE 推送到前端

---

## 二、完整代码分段解读

### 2.1 成员变量（第32-85行）

```java
@Slf4j
public class JChatMind {
    // ======================== 身份信息 ========================
    private String agentId;              // Agent UUID（数据库主键）
    private String name;                 // Agent 名称
    private String description;          // Agent 描述（前端展示）
    private String systemPrompt;         // 系统提示词（来自 Agent 配置）

    // ======================== AI 核心依赖 ========================
    private ChatClient chatClient;       // Spring AI 的 ChatClient（封装了 LLM 调用）
                                         // 可能是 DeepSeek，也可能是智谱 GLM-4.6
    private AgentState agentState;       // 当前状态（IDLE→THINKING→EXECUTING→FINISHED/ERROR）
    private List<ToolCallback> availableTools;  // 可用工具回调列表
    private List<KnowledgeBaseDTO> availableKbs; // 关联的知识库信息

    // ======================== 工具调用管理 ========================
    private ToolCallingManager toolCallingManager; // Spring AI 的工具调用管理器
                                                   // 负责解析 tool_call 并执行对应的工具

    // ======================== 聊天记忆 ========================
    private ChatMemory chatMemory;       // 对话历史（滑动窗口，保留最近 N 条）
    private String chatSessionId;        // 当前会话 ID

    // ======================== 常量 ========================
    private static final Integer MAX_STEPS = 20;          // 最大循环步数（防死循环）
    private static final Integer DEFAULT_MAX_MESSAGES = 20; // 默认消息窗口大小

    // ======================== 配置 ========================
    private ChatOptions chatOptions;     // 关闭了自动工具执行的 ChatOptions

    // ======================== 基础设施 ========================
    private SseService sseService;                      // SSE 推送服务
    private ChatMessageConverter chatMessageConverter;   // 消息转换器
    private ChatMessageFacadeService chatMessageFacadeService; // 消息持久化服务

    // ======================== 运行时状态 ========================
    private ChatResponse lastChatResponse;  // 上一次 LLM 调用的返回
    private final List<ChatMessageDTO> pendingChatMessages = new ArrayList<>();
    // ↑ 临时缓存：Agent 产生的消息暂存于此，一轮循环结束后统一通过 SSE 推送
}
```

**关键理解：**
- `availableTools` 是通过 `ToolFacadeService` 收集的 `FIXED + OPTIONAL` 工具
- `chatMemory` 是 `MessageWindowChatMemory`，只保留最近 N 条，防止超长上下文
- `pendingChatMessages` 的设计：先存进去，一轮循环结束后统一 flush，保证**消息按顺序推送**

---

### 2.2 构造函数（第90-140行）

```java
public JChatMind(String agentId, String name, String description, String systemPrompt,
                 ChatClient chatClient, Integer maxMessages,
                 List<Message> memory,                    // ← 恢复的历史消息
                 List<ToolCallback> availableTools,
                 List<KnowledgeBaseDTO> availableKbs,
                 String chatSessionId,
                 SseService sseService,
                 ChatMessageFacadeService chatMessageFacadeService,
                 ChatMessageConverter chatMessageConverter) {

    // 1. 保存基本配置
    this.agentId = agentId;
    this.name = name;
    this.systemPrompt = systemPrompt;
    this.chatClient = chatClient;
    this.availableTools = availableTools;
    this.availableKbs = availableKbs;
    this.chatSessionId = chatSessionId;

    // 2. 初始化状态
    this.agentState = AgentState.IDLE;

    // 3. 初始化聊天记忆（⭐ 核心）
    this.chatMemory = MessageWindowChatMemory.builder()
            .maxMessages(maxMessages == null ? DEFAULT_MAX_MESSAGES : maxMessages)
            .build();
    this.chatMemory.add(chatSessionId, memory);  // 恢复历史消息

    // 4. 添加系统提示词
    if (StringUtils.hasLength(systemPrompt)) {
        this.chatMemory.add(chatSessionId, new SystemMessage(systemPrompt));
    }

    // 5. ⭐⭐⭐ 关闭 Spring AI 的自动工具执行（整个架构的关键决策）
    this.chatOptions = DefaultToolCallingChatOptions.builder()
            .internalToolExecutionEnabled(false)   // ← 我们自己控制执行流程
            .build();

    // 6. 初始化工具调用管理器
    this.toolCallingManager = ToolCallingManager.builder().build();
}
```

**重点理解第5点：为什么关掉自动执行？**

Spring AI 默认的行为（`internalToolExecutionEnabled=true`）：
```
调用 chatClient.prompt().call()
  → LLM 返回 tool_call
  → Spring AI 自动调对应的工具方法
  → 把工具结果放回上下文
  → 再次调 LLM
  → LLM 返回最终回答
  → 一次 call() 全部做完
```

我们手动控制的行为（`internalToolExecutionEnabled=false`）：
```
step():
  1. think() → 调 LLM → 只拿 tool_call，不执行
  2. execute() → 我们自己决定什么时机执行工具
  3. 循环

这样做的好处：
  • 可以精确控制每一步的状态（THINKING / EXECUTING）
  • 每一步都可以持久化消息 + SSE 推送
  • 可以限制最大步数（MAX_STEPS=20）
  • 可以实现"思考→执行→再思考→再执行"的多轮推理
```

---

### 2.3 step() — 单步执行（第313-319行）

```java
private void step() {
    if (think()) {     // think() 返回 true = LLM 想调工具
        execute();     // 执行工具
    } else {           // think() 返回 false = LLM 直接回答了
        agentState = AgentState.FINISHED;  // 结束
    }
}
```

这是最简练的循环控制：
- `think()` 返回 **true**（有 tool_call）：进入 execute()
- `think()` 返回 **false**（LLM 直接回答）：任务结束

---

### 2.4 think() — 思考阶段（第220-269行）⭐⭐⭐

```java
private boolean think() {
    // 1. 构建 thinkPrompt（决策提示词）
    //    这个 prompt 告诉 LLM：你现在是一个决策模块，判断是否需要调工具
    String thinkPrompt = """
            现在你是一个智能的「决策模块」
            请根据当前对话上下文，决定下一步的动作。
            【核心原则】
            - 你可以直接回答用户问题，不需要调用任何工具
            - 仅当当前用户问题明确需要查询...才调用对应的工具
            - 不要因为之前的对话中使用了某个工具，就继续在当前问题上使用它
            - 每次独立判断当前用户提问是否需要调用工具
            【额外信息】
            - 你目前拥有的知识库列表以及描述：%s
            - 如果有缺失的上下文时，优先从知识库中进行搜索
            """.formatted(this.availableKbs);
    //                  ↑ 动态注入：告诉 LLM 有哪些知识库可用

    // 2. 从 chatMemory 中获取当前对话历史
    Prompt prompt = Prompt.builder()
            .chatOptions(this.chatOptions)
            .messages(this.chatMemory.get(this.chatSessionId))
            .build();

    // 3. ⭐ 调用 LLM（核心调用）
    this.lastChatResponse = this.chatClient
            .prompt(prompt)
            .system(thinkPrompt)              // ← thinkPrompt 通过 .system() 注入
            .toolCallbacks(this.availableTools.toArray(new ToolCallback[0]))
            .call()
            .chatClientResponse()
            .chatResponse();

    // 4. 解析 LLM 的返回
    AssistantMessage output = this.lastChatResponse.getResult().getOutput();
    List<AssistantMessage.ToolCall> toolCalls = output.getToolCalls();

    // 5. 持久化 + SSE 推送
    saveMessage(output);           // 把 AssistantMessage 存到 DB
    refreshPendingMessages();      // 把消息通过 SSE 推给前端

    // 6. 判断是否有工具调用
    return !toolCalls.isEmpty();   // 有 → 进入 execute()；无 → FINISHED
}
```

**重点理解 `.system(thinkPrompt)` vs 加到 `chatMemory` 的区别：**

| 方式 | 效果 | 问题 |
|------|------|------|
| `.system(thinkPrompt)` | 本次请求临时附加的 system 消息，**不存到** chatMemory | 每次调 LLM 都要传一次，但不会污染聊天记录 |
| 加到 `chatMemory` | 作为普通消息存进去 | 如果跑 5 轮循环，`chatMemory` 里会有 5 条 thinkPrompt，占窗口配额，用户也看得到 |

所以这里用 `.system()` 注入是**正确的设计**：thinkPrompt 只对当次 LLM 调用生效，不影响对话历史的完整性，也不浪费滑动窗口的配额。

---

### 2.5 execute() — 执行阶段（第272-310行）

```java
private void execute() {
    // 1. 安全检查
    if (!this.lastChatResponse.hasToolCalls()) {
        return;
    }

    // 2. 构建 prompt（传入当前对话历史）
    Prompt prompt = Prompt.builder()
            .messages(this.chatMemory.get(this.chatSessionId))
            .chatOptions(this.chatOptions)
            .build();

    // 3. ⭐ 执行工具调用（Spring AI 的 ToolCallingManager）
    //    它会做三件事：
    //    a. 从 lastChatResponse 中取出 AssistantMessage（含 tool_calls）
    //    b. 执行对应的工具方法（如 databaseQuery）
    //    c. 生成 ToolResponseMessage（工具调用结果）
    ToolExecutionResult toolExecutionResult = toolCallingManager
            .executeToolCalls(prompt, this.lastChatResponse);

    // 4. ⭐ 更新 chatMemory
    //    先清空旧记忆 → 添加新记忆（包含 tool_calls + tool_response 的完整上下文）
    this.chatMemory.clear(this.chatSessionId);
    this.chatMemory.add(this.chatSessionId, toolExecutionResult.conversationHistory());

    // 5. 取最后一条 ToolResponseMessage
    ToolResponseMessage toolResponseMessage = (ToolResponseMessage)
            toolExecutionResult.conversationHistory()
                    .get(toolExecutionResult.conversationHistory().size() - 1);

    // 6. 持久化 + SSE 推送
    saveMessage(toolResponseMessage);
    refreshPendingMessages();

    // 7. ⭐ 检查是否调用了 terminate 工具
    if (toolResponseMessage.getResponses().stream()
            .anyMatch(resp -> resp.name().equals("terminate"))) {
        this.agentState = AgentState.FINISHED;
        log.info("任务结束");
    }
    // 如果没有 terminate → 下一轮循环会再次进入 think()
    // Agent 会带着工具调用的结果再次思考
}
```

**重点理解第4步：为什么要 `clear + add`？**

原来的 `chatMemory` 里只有用户问题和历史对话，**没有**工具调用相关消息。
`toolCallingManager.executeToolCalls()` 会生成包含 `AssistantMessage(tool_calls)` + `ToolResponseMessage` 的完整对话历史。

所以必须：
1. 清空旧记忆
2. 用新的完整对话历史替换

否则下一轮 `think()` 看到的上下文里没有工具调用结果，没法做下一步推理。

---

### 2.6 run() — 整个 Agent 的入口（第322-343行）

```java
public void run() {
    // 1. 状态检查：只能从 IDLE 状态启动
    if (agentState != AgentState.IDLE) {
        throw new IllegalStateException("Agent is not idle");
    }

    try {
        // 2. Think-Execute 主循环（最多20步）
        for (int i = 0; i < MAX_STEPS && agentState != AgentState.FINISHED; i++) {
            int currentStep = i + 1;
            step();              // 一步 = think() + (可能) execute()

            if (currentStep >= MAX_STEPS) {
                agentState = AgentState.FINISHED;
                log.warn("Max steps reached, stopping agent");
            }
        }
        agentState = AgentState.FINISHED;  // 正常结束

    } catch (Exception e) {
        agentState = AgentState.ERROR;     // 异常结束
        log.error("Error running agent", e);
        throw new RuntimeException("Error running agent", e);
    }
}
```

**循环流程示意（以"查一下天气然后发邮件告诉我"为例）：**

```
第1步：
  think() → "用户想知道天气，我需要查城市、日期、天气"
           → LLM 返回 tool_call: getCity() + getDate()
  execute() → 执行 getCity() → "深圳"
            → 执行 getDate() → "2026-05-19"
            → 没有 terminate → 继续循环

第2步：
  think() → "现在我有城市和日期了，查天气"
           → LLM 返回 tool_call: getWeather("深圳", "2026-05-19")
  execute() → 执行 getWeather() → "25°C, 晴"
            → 没有 terminate → 继续循环

第3步：
  think() → "收到天气数据了，用户还要发邮件"
           → LLM 返回 tool_call: sendEmail("xxx@xx.com", "天气", "...")
  execute() → 执行 sendEmail() → "邮件已提交"
            → 没有 terminate → 继续循环

第4步：
  think() → "所有任务完成了，回答用户"
           → LLM 没有 tool_call（直接回答）
  → agentState = FINISHED → 循环结束
```

---

## 三、saveMessage + refreshPendingMessages（第169-217行）

```java
// saveMessage：持久化消息到数据库
private void saveMessage(Message message) {
    if (message instanceof AssistantMessage) {
        // 1. 构建 ChatMessageDTO（角色=ASSISTANT，带 toolCalls 元数据）
        // 2. 调 chatMessageFacadeService.createChatMessage(dto) → 存到 DB
        // 3. 把 DTO 加入 pendingChatMessages 队列
    } else if (message instanceof ToolResponseMessage) {
        // 1. 遍历每个 toolResponse
        // 2. 构建 ChatMessageDTO（角色=TOOL，带 toolResponse 元数据）
        // 3. 存 DB → 加入 pendingChatMessages 队列
    }
}

// refreshPendingMessages：把 pending 队列里的消息通过 SSE 推给前端
private void refreshPendingMessages() {
    for (ChatMessageDTO message : pendingChatMessages) {
        // 1. 转成 VO
        // 2. 包装成 SseMessage（type=AI_GENERATED_CONTENT）
        // 3. sseService.send(chatSessionId, sseMessage)
    }
    pendingChatMessages.clear();  // 发送完清空
}
```

**设计意图**：先持久化保证不丢数据，再推送给前端保证实时性。`pendingChatMessages` 作为一个临时的缓冲区，等一轮 step 完成后统一刷新，确保消息按顺序到达前端。

---

## 四、状态机流转

```
                     ┌──────────────────┐
                     │      IDLE        │
                     │   （空闲状态）    │
                     └────────┬─────────┘
                              │ run() 被调用
                              ▼
                     ┌──────────────────┐
                     │    THINKING      │ ← 每次进入 step() 都会
                     │   （思考中）      │   先调 think()
                     └────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
           有 tool_call            无 tool_call
                    │                   │
                    ▼                   ▼
           ┌──────────────┐   ┌──────────────────┐
           │  EXECUTING   │   │    FINISHED       │
           │  （执行中）   │   │  （正常结束）      │
           └──────┬───────┘   └──────────────────┘
                  │
          ┌───────┴───────┐
          │               │
    调用了terminate    没有terminate
          │               │
          ▼               └──→ 回到 THINKING（下一轮循环）
  ┌──────────────────┐
  │    FINISHED       │
  │  （正常结束）      │
  └──────────────────┘

异常情况：
  any step 抛出异常 → ERROR（错误结束）
  20步到了 → 强制 FINISHED
```

---

## 五、面试核心问题

### Q1: 为什么要关掉 `internalToolExecutionEnabled`？

**回答要点**：
1. **需要手动控制循环**：Spring AI 的自动执行会在一次 call() 中完成"调 LLM → 执行工具 → 再调 LLM"，我们无法插入中间的状态管理和持久化
2. **需要状态机**：关掉后每步调 LLM 只拿 tool_call，我们自己决定什么时候执行，可以精确设置 THINKING/EXECUTING 状态
3. **需要每一步持久化和推送**：每一步的结果都要存 DB + 推 SSE，自动执行模式下做不到

### Q2: Agent 最多能跑几步？超了会怎样？

20步。超了强制 FINISHED。可以改进为：
- 返回"任务太复杂，请简化"提示
- 记录断点，下次继续

### Q3: .system(thinkPrompt) 和加到 chatMemory 的区别？

见 2.4 节的对比表。核心是：.system() 不占用滑动窗口配额，不污染历史记录。

### Q4: 为什么 execute() 里要 `clear + add` 操作 chatMemory？

因为 toolCallingManager.executeToolCalls() 返回的是包含工具调用结果的完整对话历史，需要替换掉旧的（没有工具调用信息的）记忆。
