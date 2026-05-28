# JChatMind 系统性学习手册 —— AI应用工程师面试完全指南

> **定位：** 这份文档不是 Q&A 集（你已经有了），而是一份 **"从零理解到能讲清楚"的完整叙事线**。面试时你靠的不是背答案，而是对系统有"我设计过它"的全局掌控感。
>
> **使用方式：** 先通读建立全局认知 → 再对照 Q&A 文档逐个击破 → 最后对着"面试讲法"章节模拟演练

---

## 目录

1. [项目一句话定位](#1-项目一句话定位)
2. [全局架构：一张图看懂整个系统](#2-全局架构一张图看懂整个系统)
3. [后端逐层拆解：从请求到响应的每一步](#3-后端逐层拆解从请求到响应的每一步)
4. [Agent 核心：Think-Execute 循环深度拆解](#4-agent-核心think-execute-循环深度拆解)
5. [工具系统：框架化设计的精妙之处](#5-工具系统框架化设计的精妙之处)
6. [RAG 知识库：从文档上传到语义检索](#6-rag-知识库从文档上传到语义检索)
7. [SSE 实时通信：让 Agent 过程可见](#7-sse-实时通信让-agent-过程可见)
8. [多模型注册表：ChatClientRegistry 的设计](#8-多模型注册表chatclientregistry-的设计)
9. [数据模型与分层：Entity → DTO → VO 的完整链条](#9-数据模型与分层实体-dto-vo-的完整链条)
10. [前端架构：React 端的关键设计](#10-前端架构react-端的关键设计)
11. [AI 知识体系：这个项目用到了哪些 AI 概念](#11-ai-知识体系这个项目用到了哪些-ai-概念)
12. [已踩的坑与潜在风险](#12-已踩的坑与潜在风险)
13. [竞争力评估：这个项目够格吗？](#13-竞争力评估这个项目够格吗)
14. [优化路线图：怎么让它从"能用"到"能打"](#14-优化路线图怎么让它从能用到能打)
15. [面试叙事：怎么讲这个项目最出彩](#15-面试叙事怎么讲这个项目最出彩)

---

## 1. 项目一句话定位

**JChatMind 是一个 Java 实现的 AI Agent 系统，核心能力是 Think-Execute 自主决策循环——用户发一条消息后，Agent 能自主规划、调用工具、检索知识库、多步推理，直到任务完成。**

关键区别：

| 普通聊天系统 | JChatMind |
|---|---|
| 用户提问 → 调一次 LLM → 返回 | 用户提问 → Agent 循环：Think(调LLM) → Execute(调工具) → 再 Think → ... |
| 工具 = if-else | 工具 = 框架化的接口 + 自动注册 + FIXED/OPTIONAL 分类 |
| 无知识库 | RAG 全链路：上传文档 → 分块 → embedding → pgvector 向量检索 |
| 一个模型硬编码 | 注册表模式：DeepSeek / 智谱 可切换，新增 3 行配置 |
| 等待完整回复 | SSE 实时推送：THINKING → EXECUTING → DONE |

**面试核心话术：** "这不是一个聊天机器人项目，而是一个 Agent 系统。区别在于 Agent 有自主决策能力——它会自己决定要不要调工具、调哪个工具、什么时候结束。"

---

## 2. 全局架构：一张图看懂整个系统

### 2.1 物理结构

```
D:\SelfLearn\JChatMind\
├── jchatmind/                  ← 后端（Spring Boot + Spring AI）
│   ├── pom.xml                 ← Maven 依赖：Spring AI 1.1 + MyBatis + PostgreSQL
│   └── src/main/java/com/kama/jchatmind/
│       ├── agent/              ← 🔥 Agent 核心（JChatMind + Factory + 状态机）
│       │   ├── tools/          ← 工具实现（KnowledgeTool, DataBaseTool, EmailTool...）
│       │   └── examples/       ← 早期版本（V1/V2，学习用，不影响主流程）
│       ├── config/             ← 配置类（ChatClientRegistry, AsyncConfig, CORS）
│       ├── controller/         ← 8 个 REST 控制器
│       ├── converter/          ← Entity↔DTO↔VO 转换器
│       ├── event/              ← 事件驱动（ChatEvent + Listener）
│       ├── exception/          ← 全局异常处理
│       ├── mapper/             ← MyBatis Mapper 接口
│       ├── message/            ← SSE 消息体定义
│       ├── model/              ← 数据模型五层（entity/dto/vo/request/response）
│       ├── service/            ← 服务接口 + 实现
│       └── typehandler/        ← MyBatis 自定义类型处理器（pgvector）
├── ui/                         ← 前端（React 19 + TypeScript + Ant Design X）
│   └── src/
│       ├── api/                ← HTTP 请求层（api.ts + http.ts）
│       ├── components/         ← UI 组件（聊天、知识库、Agent 管理）
│       ├── hooks/              ← 自定义 Hook（useAgents, useChatSessions...）
│       ├── types/              ← TypeScript 类型定义
│       └── contexts/           ← React Context
├── jchatmind_v2/               ← 数据库建表 SQL + 测试数据
├── data/                       ← 文档存储目录
├── 学习文档/                    ← 项目详解系列文档
└── examples/                   ← 前端示例 HTML
```

### 2.2 运行时架构（请求全链路）

```
用户浏览器
  │ POST /api/chat-messages {agentId, sessionId, role:"user", content:"..."}
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Controller 层                                                   │
│ ChatMessageController.createChatMessage()                       │
│   → 调用 ChatMessageFacadeService.createChatMessage(request)    │
│   → HTTP 200 返回 {chatMessageId}（此时 Agent 还没执行）          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ Facade 服务层                                                   │
│ ChatMessageFacadeServiceImpl.createChatMessage()                │
│   ① doCreateChatMessage() → 持久化 UserMessage 到 DB            │
│   ② publisher.publishEvent(new ChatEvent(...))                  │
│   ③ 返回 chatMessageId                                          │
└───────────────────────┬─────────────────────────────────────────┘
                        │ Spring ApplicationEvent（内存中传递）
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 异步事件层                                                      │
│ @Async ChatEventListener.handle(ChatEvent)                      │
│   在 async-event-* 线程池中执行（core=4, max=10）                │
│   → JChatMindFactory.create(agentId, sessionId)                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ Factory 装配阶段（这是很多人忽略的关键环节）                       │
│ JChatMindFactory.create()                                       │
│   ① loadAgent(agentId)         → 查 DB 获取 Agent 配置          │
│   ② toAgentConfig(agent)       → JSONB 反序列化为 AgentDTO      │
│   ③ loadMemory(sessionId)      → 恢复最近 N 条消息为 Message[]   │
│   ④ resolveRuntimeKnowledgeBases() → 查关联知识库                │
│   ⑤ resolveRuntimeTools()      → FIXED + 匹配的 OPTIONAL        │
│   ⑥ buildToolCallbacks()       → Tool → ToolCallback            │
│   ⑦ registry.get(modelName)    → 获取对应模型的 ChatClient       │
│   ⑧ return new JChatMind(...)  → 组装完整 Agent 实例            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent 核心层                                                    │
│ JChatMind.run()                                                 │
│   for (i = 0; i < MAX_STEPS && state != FINISHED; i++) {        │
│     step()                                                      │
│       ├─ think(): 调 LLM → 有 tool_calls?                       │
│       │    ├─ 有 → 返回 true                                    │
│       │    └─ 无 → state = FINISHED, 返回 false                 │
│       └─ execute(): 工具执行 → 持久化 → SSE 推送                 │
│          └─ 检查 terminate → 是则 state = FINISHED               │
│   }                                                             │
│   state = FINISHED（兜底）                                       │
└───────────────────────┬─────────────────────────────────────────┘
                        │ 每步产出消息
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 持久化 + SSE 推送                                                │
│ saveMessage()      → 写入 chat_message 表                       │
│ refreshPendingMessages() → SseService.send(sessionId, SseMessage)│
│   → 前端 EventSource 收到事件 → 实时渲染到聊天界面               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 你需要记住的核心数字

| 参数 | 值 | 含义 |
|------|------|------|
| MAX_STEPS | 20 | Agent 最大循环步数（安全阀） |
| maxMessages | 20（默认）/ 可配置 | ChatMemory 滑动窗口大小 |
| MAX_TOOL_RESPONSE_LENGTH | 300 | 工具返回结果截断长度 |
| SSE 超时 | 30 分钟 | SseEmitter 过期时间 |
| @Async 线程池 | core=4, max=10, queue=100 | 异步处理能力 |
| Embedding 维度 | 1024 | bge-m3 模型输出维度 |
| 向量检索 top-K | 3 | 相似度返回片段数 |

---

## 3. 后端逐层拆解：从请求到响应的每一步

### 3.1 Controller 层（8 个控制器，各自职责清晰）

| 控制器 | 路径 | 职责 | 关键方法 |
|--------|------|------|---------|
| `ChatMessageController` | `/api/chat-messages*` | 消息 CRUD，**Agent 对话的入口** | `createChatMessage()` — 触发 Agent 执行 |
| `ChatSessionController` | `/api/chat-sessions*` | 会话管理 | CRUD + 按 agentId 查询 |
| `AgentController` | `/api/agents*` | Agent 配置管理 | CRUD |
| `KnowledgeBaseController` | `/api/knowledge-bases*` | 知识库管理 | CRUD |
| `DocumentController` | `/api/documents*` | 文档上传/管理 | `uploadDocument()` — 触发 RAG 处理 |
| `SseController` | `/sse/connect/{id}` | SSE 连接建立 | `connect()` — 返回 SseEmitter |
| `ToolController` | `/api/tools` | 工具列表查询 | 返回 OPTIONAL 类型工具 |
| `TestController` | `/health` | 健康检查 | Actuator 端点 |

**关键理解：** `ChatMessageController.createChatMessage()` 是整个系统的对话入口。用户发消息，Controller 只做两件事：① 持久化消息 ② 发事件，然后立即返回 200。Agent 的执行完全在后台异步进行。

### 3.2 Facade 服务层（外观模式，业务编排）

Facade 层的核心作用：**对 Controller 提供统一接口，屏蔽底层 Mapper/Service 的复杂性。**

每个 FacadeService 做的事是类似的：
1. 接收 Request → 转 DTO → 转 Entity
2. 调 Mapper 做数据库操作
3. 转 VO → 包装 Response 返回

唯一有特殊逻辑的是 `ChatMessageFacadeServiceImpl`：

```java
public CreateChatMessageResponse createChatMessage(CreateChatMessageRequest request) {
    // ① 先持久化消息（保证用户消息不丢）
    ChatMessage chatMessage = doCreateChatMessage(request);
    
    // ② 发布事件（触发 Agent 异步执行）
    publisher.publishEvent(new ChatEvent(
        request.getAgentId(),
        chatMessage.getSessionId(),
        chatMessage.getContent()
    ));
    
    // ③ 立即返回（不等 Agent 执行完）
    return CreateChatMessageResponse.builder()
            .chatMessageId(chatMessage.getId())
            .build();
}
```

**面试要讲的设计思想：** "先持久化再发事件"是经典的**最终一致性**模式——即使事件处理失败，用户消息已经存进去了，不会丢。

### 3.3 事件驱动层

```
ChatEvent（简单的 POJO）
  ├── agentId
  ├── sessionId
  └── userInput

ChatEventListener（@Component + @Async + @EventListener）
  └─ handle(ChatEvent event) {
       JChatMind agent = factory.create(event.agentId, event.sessionId);
       agent.run();  // 异步执行，不阻塞 HTTP 线程
     }
```

`@Async` 配置在 `AsyncConfig.java` 中：
- `@EnableAsync` 开启异步支持
- 线程池：`corePoolSize=4, maxPoolSize=10, queueCapacity=100`
- 线程名前缀：`async-event-`

**面试重点：** 为什么用 `@Async` 而不是 CompletableFuture？
- `@Async` 更简单，Spring 原生支持，不需要手动管理 Future
- 如果需要返回值或更精细的控制，可以用 CompletableFuture
- 如果需要可靠性（消息不丢），应该引入消息队列（RabbitMQ/Kafka）

### 3.4 Converter 层（数据形态转换）

项目有 6 个 Converter，每个负责三种转换方向：

```
Entity ←→ DTO ←→ VO
 ↑                ↑
数据库层          前端展示层
       DTO ←→ Request/Response
            API 契约层
```

**为什么要分这么多层？** （Q23 的完整回答）

1. **安全隔离**：Entity 有敏感字段（虽然这个项目没有密码，但生产系统有）
2. **类型适配**：数据库存 JSON String → DTO 转为 `List<String>` → 前端直接用
3. **解耦变更**：数据库加字段不影响前端 API，前端改展示不影响数据库

**以 Agent 为例走一遍转换过程：**

```
数据库 Agent 表（JSONB 字段是 String）
  ↓ AgentConverter.toDTO()
AgentDTO（allowedTools 从 String → List<String>）
  ↓ AgentConverter.toVO()
AgentVO（给前端用，类型安全）
```

关键点：`AgentConverter.toDTO()` 使用 `objectMapper.readValue(json, new TypeReference<List<String>>(){})` 把 JSONB 字符串反序列化为 Java 集合。这就是为什么需要 Converter —— MyBatis 读 JSONB 返回的是 String，不能直接用。

### 3.5 Mapper 层（MyBatis）

6 个 Mapper 接口 + 6 个 XML 文件：

| Mapper | 关键 SQL |
|--------|---------|
| `AgentMapper` | CRUD + 按 ID 查询 |
| `ChatMessageMapper` | `selectBySessionId` + `selectBySessionIdRecently`（DESC + LIMIT，用于恢复记忆） |
| `ChatSessionMapper` | CRUD + 按 agentId 查询 |
| `ChunkBgeM3Mapper` | `similaritySearch` — 核心向量检索 SQL |
| `DocumentMapper` | CRUD + 按 kbId 查询 |
| `KnowledgeBaseMapper` | CRUD + 批量查询 `selectByIdBatch` |

**最值得关注的 Mapper：** `ChunkBgeM3Mapper.xml` 中的 `similaritySearch`：

```sql
SELECT * FROM chunk_bge_m3
WHERE kb_id = CAST(#{kbId} AS uuid)
ORDER BY embedding <-> #{vectorLiteral}::vector
LIMIT #{limit}
```

- `<->` 是 pgvector 的**欧氏距离**运算符
- `CAST(...AS uuid)` 确保类型匹配
- `#{vectorLiteral}` 是由 `RagServiceImpl.toPgVector(float[])` 生成的 `[0.1,0.2,...]` 字符串

### 3.6 TypeHandler（MyBatis 扩展机制）

`PgVectorTypeHandler` 处理 `float[]` ↔ pgvector `VECTOR(1024)` 的双向映射：

- 写入时：`float[]` → `[0.1,0.2,...]` 字符串 → `ps.setObject(i, str, Types.OTHER)`
- 读取时：pgvector 字符串 → 去掉 `[]` → `split(",")` → `float[]`

**面试要点：** 这是 MyBatis 的扩展点之一，TypeHandler 解决了"ORM 框架不认识数据库扩展类型"的问题。类似的场景：处理 JSON 类型、枚举、自定义数据格式。

---

## 4. Agent 核心：Think-Execute 循环深度拆解

这是整个项目的灵魂，也是面试必考。你要能从头到尾讲清楚每一步在做什么。

### 4.1 状态机

```java
public enum AgentState {
    IDLE,      // 空闲（初始状态）
    PLANNING,  // 计划中（当前代码未使用，预留）
    THINKING,  // 思考中（当前代码未使用，状态直接在 run() 中管理）
    EXECUTING, // 执行中（同上）
    FINISHED,  // 正常结束
    ERROR      // 异常结束
}
```

**注意：** 实际代码中 PLANNING/THINKING/EXECUTING 这三个状态**并未被设置**，状态直接从 IDLE → FINISHED/ERROR。SSE 推送的状态（AI_THINKING/AI_EXECUTING）是前端根据消息类型推断的，不是 Agent 内部状态。这是一个设计上的简化，面试时如果被问到，可以说"这是预留的扩展点，当前简化了状态转换"。

### 4.2 Think-Execute 循环完整代码走读

```java
public void run() {
    // ① 状态检查：只有 IDLE 状态才能开始
    if (agentState != AgentState.IDLE) {
        throw new IllegalStateException("Agent is not idle");
    }

    try {
        // ② 主循环：最多 MAX_STEPS 步
        for (int i = 0; i < MAX_STEPS && agentState != AgentState.FINISHED; i++) {
            step();  // 单步执行
            
            // ③ 超步兜底
            if (currentStep >= MAX_STEPS) {
                agentState = AgentState.FINISHED;
                log.warn("Max steps reached, stopping agent");
            }
        }
        agentState = AgentState.FINISHED;
    } catch (Exception e) {
        // ④ 异常处理：设置 ERROR 状态
        agentState = AgentState.ERROR;
        throw new RuntimeException("Error running agent", e);
    }
}
```

```java
private void step() {
    if (think()) {   // 返回 true = 有工具要调
        execute();    // 执行工具
    } else {         // 返回 false = 没有工具，LLM 直接回答了
        agentState = AgentState.FINISHED;
    }
}
```

### 4.3 think() 方法 —— 与 LLM 对话的核心

```java
private boolean think() {
    // ① 构建系统提示词：工具选择规则 + 知识库信息
    String thinkToolRules = """
        判断意图并选择工具：
        - 用户问天气 → 调用 queryWeather
        - 用户查知识库/文档 → 调用 KnowledgeTool
        - 其他 → 直接回答
        
        【重要规则】
        1. 如果工具结果已存在于对话中，直接用结果回答
        2. 不参考旧对话，只看本轮最新上下文
        
        知识库：%s
        """.formatted(this.availableKbs);

    // ② 合并系统提示词
    String thinkPrompt = StringUtils.hasLength(this.systemPrompt)
            ? this.systemPrompt + "\n\n---\n\n" + thinkToolRules
            : thinkToolRules;

    // ③ 截取最后一条用户消息及之后的所有消息
    //    目的：避免重复工具调用（让 LLM 看到工具返回结果）
    List<Message> fullHistory = this.chatMemory.get(this.chatSessionId);
    List<Message> thinkMessages = new ArrayList<>();
    int lastUserIdx = -1;
    for (int i = fullHistory.size() - 1; i >= 0; i--) {
        if (fullHistory.get(i) instanceof UserMessage) {
            lastUserIdx = i;
            break;
        }
    }
    if (lastUserIdx >= 0) {
        thinkMessages.addAll(fullHistory.subList(lastUserIdx, fullHistory.size()));
    }

    // ④ 构建 Prompt（使用 ChatOptions 关闭自动工具执行）
    Prompt prompt = Prompt.builder()
            .chatOptions(this.chatOptions)  // internalToolExecutionEnabled=false
            .messages(thinkMessages)
            .build();

    // ⑤ 调用 LLM（通过 Spring AI 的 ChatClient）
    this.lastChatResponse = this.chatClient
            .prompt(prompt)
            .system(thinkPrompt)          // 系统提示词（不入 chatMemory）
            .toolCallbacks(this.availableTools.toArray(new ToolCallback[0]))
            .call()
            .chatClientResponse()
            .chatResponse();

    // ⑥ 提取工具调用决策
    AssistantMessage output = lastChatResponse.getResult().getOutput();
    List<AssistantMessage.ToolCall> toolCalls = output.getToolCalls();

    // ⑦ 持久化 AssistantMessage + SSE 推送
    saveMessage(output);
    refreshPendingMessages();

    // ⑧ 返回：有工具调用 = true，无 = false
    return !toolCalls.isEmpty();
}
```

**think() 中的关键设计决策：**

**Q：为什么只取最后一条用户消息及之后的消息，而不是全部历史？**

A：防止 LLM 重复调用工具。假设流程是：
1. 用户问"北京天气" → LLM 调 queryWeather → 得到结果
2. execute() 把结果存入 chatMemory
3. 下一轮 think() 如果再传全部历史，LLM 可能**又**看到"北京天气"这个问题，再次调用 queryWeather

只取最后一条用户消息 + 之后的工具结果，LLM 就能看到"我已经查过天气了，结果在这"，直接回答。

**Q：为什么用 `.system()` 注入 thinkPrompt 而不是 `chatMemory.add(new SystemMessage(...))`？**

A：三个原因（Q3 的完整回答）：
1. **窗口配额**：chatMemory 最多 20 条，thinkPrompt 每轮新增一条，5 轮就占 1/4
2. **优先级**：`.system()` 是系统级约束，加进 chatMemory 变普通消息，优先级被稀释
3. **冗余**：每次 think() 都生成新的 thinkPrompt（知识库可能变了），旧的留在 chatMemory 里就是垃圾

### 4.4 execute() 方法 —— 工具执行与结果处理

```java
private void execute() {
    // ① 构建 Prompt（包含完整对话历史）
    Prompt prompt = Prompt.builder()
            .messages(this.chatMemory.get(this.chatSessionId))
            .chatOptions(this.chatOptions)
            .build();

    // ② 通过 Spring AI 的 ToolCallingManager 执行工具
    //    注意：虽然是"手动执行"，但还是用 Spring AI 的能力
    ToolExecutionResult toolExecutionResult = 
            toolCallingManager.executeToolCalls(prompt, this.lastChatResponse);

    // ③ 获取工具返回的 ToolResponseMessage
    Message lastMsg = conversationHistory.get(conversationHistory.size() - 1);
    ToolResponseMessage toolResponseMessage = (ToolResponseMessage) lastMsg;

    // ④ 截断工具返回结果（防止大量文本干扰 LLM）
    List<ToolResponseMessage.ToolResponse> truncatedResponses = 
            toolResponseMessage.getResponses().stream()
                .map(resp -> {
                    String data = resp.responseData();
                    if (data != null && data.length() > MAX_TOOL_RESPONSE_LENGTH) {
                        data = data.substring(0, MAX_TOOL_RESPONSE_LENGTH) + "...(内容过长已截断)";
                    }
                    return new ToolResponseMessage.ToolResponse(resp.id(), resp.name(), data);
                })
                .toList();

    // ⑤ 更新 chatMemory（替换为截断后的版本）
    this.chatMemory.clear(this.chatSessionId);
    this.chatMemory.add(this.chatSessionId, truncatedHistory);

    // ⑥ 持久化 ToolResponseMessage + SSE 推送
    saveMessage(toolResponseMessage);
    refreshPendingMessages();

    // ⑦ 检查 terminate 工具 → 决定是否结束
    if (toolResponseMessage.getResponses().stream()
            .anyMatch(resp -> resp.name().equals("terminate"))) {
        this.agentState = AgentState.FINISHED;
    }
}
```

**execute() 中的关键设计：**

**Q：为什么要截断工具返回结果到 300 字符？**

A：工具返回可能很大（比如数据库查询返回 100 行数据），直接放入 chatMemory 会：
1. 占满上下文窗口，挤压有用的对话
2. 干扰 LLM 的后续决策（太多噪声信息）
3. 浪费 Token（多花钱）

截断到 300 字符，保留关键信息，其余丢弃。LLM 如果需要更多信息，可以再次调用工具。

**Q：`chatMemory.clear()` + `chatMemory.add()` 是什么意思？**

A：把原始的 conversationHistory（含未截断的工具结果）清空，替换为截断后的版本。这是**在 chatMemory 层面做截断**，保证 LLM 下一轮看到的也是截断后的结果。但注意：DB 中存储的仍是完整内容（saveMessage 在截断之前调用的）。

### 4.5 终止条件的三条路径

```
路径 1: think() 返回 false（LLM 没有调用任何工具，直接回答了）
  → step() 中 agentState = FINISHED

路径 2: execute() 检测到 terminate 工具被调用
  → agentState = FINISHED

路径 3: run() 循环达到 MAX_STEPS（20 步）
  → 强制 agentState = FINISHED
```

这三条路径**独立工作**，互不依赖。MAX_STEPS 是安全阀（不管 LLM 怎么想，到了就停），terminate 是主动结束（LLM 自己决定结束），think() 返回 false 是自然结束（LLM 认为不需要再调工具了）。

---

## 5. 工具系统：框架化设计的精妙之处

### 5.1 接口定义

```java
public interface Tool {
    String getName();        // 工具名（必须与 @Tool(name) 一致）
    String getDescription(); // 描述
    ToolType getType();      // FIXED 或 OPTIONAL
}
```

```java
public enum ToolType {
    FIXED,    // 系统强制，所有 Agent 都有（如 KnowledgeTool, TerminateTool）
    OPTIONAL, // 可选，按 Agent 配置启用（如 DataBaseTool, EmailTool）
}
```

### 5.2 注册机制

```
每个 Tool 实现类加 @Component
  → Spring 自动扫描
  → 注入 ToolFacadeServiceImpl 中的 List<Tool>
  → 按 ToolType 分类过滤
```

```java
@Service
@AllArgsConstructor
public class ToolFacadeServiceImpl implements ToolFacadeService {
    private final List<Tool> tools;  // Spring 自动收集所有 @Component Tool

    public List<Tool> getFixedTools() {
        return tools.stream().filter(t -> t.getType() == ToolType.FIXED).toList();
    }
    public List<Tool> getOptionalTools() {
        return tools.stream().filter(t -> t.getType() == ToolType.OPTIONAL).toList();
    }
}
```

### 5.3 工具到 ToolCallback 的转换

Spring AI 的 `@Tool` 注解 + `MethodToolCallbackProvider` 把 Java 方法转为 LLM 可调用的工具：

```java
// 在 KnowledgeTools 中
@org.springframework.ai.tool.annotation.Tool(
    name = "KnowledgeTool",
    description = "从指定知识库中执行相似性检索..."
)
public String knowledgeQuery(String kbsId, String query) { ... }
```

Factory 中的转换：

```java
private List<ToolCallback> buildToolCallbacks(List<Tool> runtimeTools) {
    for (Tool tool : runtimeTools) {
        ToolCallback[] toolCallbacks = MethodToolCallbackProvider.builder()
                .toolObjects(tool)  // 传入 Tool 实例
                .build()
                .getToolCallbacks();  // Spring AI 解析 @Tool 注解，生成 ToolCallback
        callbacks.addAll(Arrays.asList(toolCallbacks));
    }
}
```

### 5.4 工具一览

| 工具名 | 类型 | 作用 | 入参 | 返回 |
|--------|------|------|------|------|
| `KnowledgeTool` | FIXED | RAG 知识库检索 | kbsId, query | 相似文本片段 |
| `terminate` | FIXED | 终止 Agent 循环 | 无（void） | void → ToolResponse |
| `databaseQuery` | OPTIONAL | SQL 查询（只读） | sql | 格式化表格 |
| `sendEmail` | OPTIONAL | 发送邮件 | to, subject, content | 发送结果 |
| `queryWeather` | OPTIONAL | 天气查询 | city | 天气信息 |
| `FileSystemTools` | - | 禁用 | - | - |
| `DirectAnswerTool` | - | 禁用 | - | - |

### 5.5 已知坑：getName() 和 @Tool(name) 不一致

`WeatherTools` 曾出现此问题：`getName()` 返回 `"weatherTool"`，但 `@Tool(name = "queryWeather")`。这导致：
- 前端工具列表显示的名字 = getName() = "weatherTool"
- LLM 能调用的工具名 = @Tool(name) = "queryWeather"
- 两者不匹配，前端看到的名字和实际可调用的名字不一致

**修复方法：** 统一两者。**更好的做法：** 用 Spring 的 BeanPostProcessor 在启动时自动校验一致性。

---

## 6. RAG 知识库：从文档上传到语义检索

### 6.1 写入端（Ingestion Pipeline）

```
用户上传 Markdown 文件
  │
  ▼
DocumentController.uploadDocument(kbId, file)
  │
  ▼
DocumentFacadeServiceImpl.uploadDocument()
  ├── ① 提取文件信息（文件名、类型、大小）
  ├── ② 创建 Document 记录（写入 document 表）
  ├── ③ 保存文件到磁盘（DocumentStorageService）
  ├── ④ 更新 Document 记录（保存文件路径到 metadata）
  └── ⑤ 如果是 Markdown → processMarkdownDocument()
        │
        ▼
      MarkdownParserServiceImpl.parseMarkdown(inputStream)
        ├── 用 Flexmark 解析 Markdown AST
        ├── 按顶层标题分块（每个 ## 级标题一个 section）
        └── 返回 List<MarkdownSection>（每个 section 有 title + content）
        │
        ▼
      遍历每个 section：
        ├── ragService.embed(title) → 调 Ollama(bge-m3) 生成 1024 维向量
        ├── 构建 ChunkBgeM3 实体（kbId, docId, content=section内容, embedding=向量）
        └── chunkBgeM3Mapper.insert(chunk) → 存入 chunk_bge_m3 表
```

### 6.2 读取端（Retrieval Pipeline）

```
Agent think() 中 LLM 决定调用 KnowledgeTool
  │
  ▼
KnowledgeTools.knowledgeQuery(kbsId, query)
  │
  ▼
RagServiceImpl.similaritySearch(kbId, query)
  ├── ① ragService.embed(query) → 调 Ollama(bge-m3) 生成查询向量
  ├── ② toPgVector(float[]) → 转为 "[0.1,0.2,...]" 字符串
  └── ③ chunkBgeM3Mapper.similaritySearch(kbId, vector, 3)
        │
        ▼ SQL:
        SELECT * FROM chunk_bge_m3
        WHERE kb_id = CAST(#{kbId} AS uuid)
        ORDER BY embedding <-> #{vectorLiteral}::vector
        LIMIT 3
        │
        ▼
      返回 top-3 最相似的 chunk
      → 提取 content 字段 → String.join("\n") → 返回给 LLM
```

### 6.3 关键技术点

**Embedding 模型选择：** bge-m3（Ollama 本地部署）
- 维度：1024
- 为什么本地部署？免费、无网络延迟、数据不出内网
- 缺点：速度慢于云端 API、需要 GPU

**向量索引：** ivfflat
```sql
CREATE INDEX idx_chunk_embedding
ON chunk_bge_m3
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);
```
- `vector_l2_ops` = 使用欧氏距离（与 `<->` 运算符匹配）
- `lists = 100` = 聚类数（偏少，经验公式 `sqrt(N)`，10 万条应该 ~317）

**分块策略：** 按 Markdown 顶层标题分块
- 优点：简单、语义完整性好（标题下的内容通常相关）
- 缺点：一个大标题下可能有几千字，块太大；不支持无标题的文档
- 改进：重叠分块（相邻块重叠 10-20%）、分层分块、固定 Token 数切分

---

## 7. SSE 实时通信：让 Agent 过程可见

### 7.1 架构

```
后端：
  SseController → SseServiceImpl
  ConcurrentHashMap<String, SseEmitter> clients
  SseEmitter 超时 = 30 分钟

前端：
  new EventSource(`${baseRoot}/sse/connect/${chatSessionId}`)
  es.addEventListener("message", (event) => { ... })
```

### 7.2 消息类型（SseMessage.Type）

| 类型 | 含义 | Payload 内容 |
|------|------|-------------|
| `AI_GENERATED_CONTENT` | Agent 产生了新消息 | `{message: ChatMessageVO}` |
| `AI_PLANNING` | Agent 正在规划 | `{statusText: "正在规划..."}` |
| `AI_THINKING` | Agent 正在思考 | `{statusText: "正在思考..."}` |
| `AI_EXECUTING` | Agent 正在执行工具 | `{statusText: "正在执行..."}` |
| `AI_DONE` | Agent 执行完成 | `{done: true}` |

**重要发现：** 当前后端代码中，JChatMind.java 只发送了 `AI_GENERATED_CONTENT` 类型的消息（在 `refreshPendingMessages()` 中），并没有发送 AI_PLANNING/AI_THINKING/AI_EXECUTING/AI_DONE。但前端 AgentChatView.tsx 中却在监听这些类型。这意味着：
1. 要么是后端还未实现这些状态推送（可能是 TODO）
2. 要么是在其他版本中实现的

这是你可以**主动优化**的地方——在 think() 和 execute() 开始/结束时发送对应的状态消息。

### 7.3 SSE 断连行为

当用户刷新页面时：
1. `SseEmitter` 触发 `onCompletion` 回调 → `clients.remove(chatSessionId)`
2. 后端 `@Async` 线程继续执行 Agent
3. `send()` 时发现 `emitter == null` → 抛异常 "No client found"
4. Agent 执行结果仍会持久化到 DB，用户重新打开页面后通过 REST API 加载历史

**面试要讲的点：** "Agent 不会因为 SSE 断开而停止——消息持久化保证了数据不丢。但用户看不到实时状态，体验不好。优化方向是：加'运行中'状态标识，用户重连后自动推送积压消息。"

### 7.4 SSE vs WebSocket 选择

| 维度 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（服务端→客户端） | 双向 |
| 协议 | HTTP | 独立的 ws:// 协议 |
| 浏览器支持 | 原生 EventSource | 需要库或原生 API |
| 自动重连 | 有 | 需手动实现 |
| 二进制支持 | 无 | 有 |
| 适用场景 | 通知/推送 | 实时交互（游戏/协同编辑） |

**JChatMind 选 SSE 的理由：** Agent 执行状态只需要单向推送（后端→前端），不需要前端→后端的实时通信。SSE 更简单、更轻量。

---

## 8. 多模型注册表：ChatClientRegistry 的设计

### 8.1 实现机制

```java
@Configuration
public class MultiChatClientConfig {
    @Bean("deepseek-chat")
    public ChatClient deepSeekChatClient(DeepSeekChatModel deepSeekChatModel) {
        return ChatClient.create(deepSeekChatModel);
    }

    @Bean("glm-4.6")
    public ChatClient zhiPuAiChatClient(ZhiPuAiChatModel zhiPuAiChatModel) {
        return ChatClient.create(zhiPuAiChatModel);
    }
}

@Component
public class ChatClientRegistry {
    private final Map<String, ChatClient> chatClients;

    public ChatClientRegistry(Map<String, ChatClient> chatClients) {
        this.chatClients = chatClients;  // Spring 自动注入所有 ChatClient Bean
    }

    public ChatClient get(String key) {
        return chatClients.get(key);  // 按 Bean 名称查找
    }
}
```

### 8.2 使用流程

```
Agent 表 model 字段 = "deepseek-chat"
  ↓ JChatMindFactory.buildAgentRuntime()
ChatClient chatClient = chatClientRegistry.get("deepseek-chat")
  ↓ 返回 MultiChatClientConfig 中 @Bean("deepseek-chat") 创建的实例
JChatMind 构造函数中接收 chatClient
  ↓ think() 中调用
this.chatClient.prompt(prompt).system(...).toolCallbacks(...).call()
```

### 8.3 配置来源

`application.yaml` 中：

```yaml
spring:
  ai:
    deepseek:
      api-key: sk-xxx
      base-url: https://api.deepseek.com
      chat:
        options:
          model: deepseek-chat
    zhipuai:
      api-key: xxx
      base-url: https://open.bigmodel.cn/api/paas
      chat:
        options:
          model: glm-4.6
```

Spring AI 的自动配置会根据这些配置创建 `DeepSeekChatModel` 和 `ZhiPuAiChatModel`，然后在 `MultiChatClientConfig` 中包装为 `ChatClient`。

### 8.4 新增模型需要改什么

1. `pom.xml` 加对应的 Spring AI starter（如 `spring-ai-starter-model-openai`）
2. `application.yaml` 加配置
3. `MultiChatClientConfig` 加一个 `@Bean` 方法
4. `AgentDTO.ModelType` 枚举加一项

**不需要改：** 任何业务代码（JChatMind、Factory、Controller、Service）

---

## 9. 数据模型与分层：Entity → DTO → VO 的完整链条

### 9.1 数据库表（6 张）

```sql
agent            -- Agent 配置（name, system_prompt, model, allowed_tools JSONB, ...）
chat_session     -- 聊天会话（关联 agent_id）
chat_message     -- 聊天消息（session_id, role, content, metadata JSONB）
knowledge_base   -- 知识库（name, description）
document         -- 文档（kb_id, filename, filetype, metadata JSONB）
chunk_bge_m3     -- 文档分块 + 向量（kb_id, doc_id, content, embedding VECTOR(1024)）
```

### 9.2 五层数据模型

```
Entity    ← 与数据库表一一对应（MyBatis 操作这一层）
  ↓ Converter
DTO       ← 业务传输对象（JSONB 字段反序列化为 Java 类型）
  ↓ Converter
VO        ← 前端展示视图对象（脱敏、格式化）
  ↓
Request   ← API 请求体
Response  ← API 响应体
```

**以 ChatMessage 为例走完整链条：**

```
数据库 chat_message 表
  │ role = "assistant", metadata = '{"toolCalls":[{"id":"call_1","name":"queryWeather","arguments":"{\"city\":\"北京\"}"}]}'
  │ （metadata 是 JSON String）
  ▼
ChatMessage Entity
  │ role: String, metadata: String
  ▼ ChatMessageConverter.toDTO()
ChatMessageDTO
  │ role: RoleType.ASSISTANT (枚举), 
  │ metadata: MetaData { toolCalls: List<AssistantMessage.ToolCall> }
  │ （JSON String → Java 对象）
  ▼ ChatMessageConverter.toVO()
ChatMessageVO
  │ 返回给前端
```

### 9.3 JSONB 字段的特殊处理

Agent 表的 `allowed_tools`、`allowed_kbs`、`chat_options` 都是 JSONB 类型：

```
数据库: allowed_tools = '["KnowledgeTool","dataBaseTool"]'  (String)
  ↓ AgentConverter.toDTO()
Java:   allowedTools = List.of("KnowledgeTool", "dataBaseTool")  (List<String>)

数据库: chat_options = '{"temperature":0.7,"topP":1.0,"messageLength":20}'  (String)
  ↓ AgentConverter.toDTO()
Java:   chatOptions = ChatOptions(temperature=0.7, topP=1.0, messageLength=20)
```

使用的 Jackson 工具：`objectMapper.writeValueAsString()`（序列化）和 `objectMapper.readValue(json, TypeReference)`（反序列化）。

---

## 10. 前端架构：React 端的关键设计

### 10.1 技术栈

- React 19 + TypeScript 5.9
- Ant Design 6 + Ant Design X 2（AI 聊天组件库）
- Tailwind CSS 4
- Vite 构建

### 10.2 核心组件

```
App.tsx
  ├── JChatMindLayout.tsx     ← 布局（侧边栏 + 内容区）
  │   ├── Sidebar.tsx         ← 侧边栏导航
  │   └── Content.tsx         ← 内容区（路由出口）
  │
  ├── ChatTabContent.tsx      ← 聊天标签页
  │   ├── AgentChatView.tsx   ← 🔥 核心：聊天界面
  │   │   ├── AgentChatHistory.tsx   ← 消息气泡列表
  │   │   ├── AgentChatInput.tsx     ← 输入框
  │   │   └── EmptyAgentChatView.tsx ← 空状态
  │   └── ChatSessionsContext.tsx    ← 会话状态管理
  │
  ├── AgentTabContent.tsx     ← Agent 管理标签页
  │   └── AddAgentModal.tsx   ← 创建/编辑 Agent 弹窗
  │
  └── KnowledgeBaseTabContent.tsx  ← 知识库标签页
      ├── KnowledgeBaseView.tsx     ← 知识库详情
      └── AddKnowledgeBaseModal.tsx ← 创建知识库弹窗
```

### 10.3 核心交互流程（AgentChatView.tsx）

```
用户输入消息 → handleSendMessage()
  │
  ├── 如果没有 chatSessionId（首次对话）
  │   ├── createChatSession() → 创建新会话
  │   ├── createChatMessage() → 发送首条消息
  │   └── navigate(`/chat/${newSessionId}`)
  │
  └── 如果有 chatSessionId
      ├── createChatMessage() → 发送消息
      └── 等待 SSE 推送新消息

SSE 连接：
  new EventSource(`${baseRoot}/sse/connect/${chatSessionId}`)
  │
  ├── addEventListener("message") → 收到 SseMessage
  │   ├── type = AI_GENERATED_CONTENT → addMessage() 添加到消息列表
  │   ├── type = AI_THINKING → 显示"思考中"状态
  │   ├── type = AI_EXECUTING → 显示"执行中"状态
  │   └── type = AI_DONE → 隐藏状态
  │
  └── addEventListener("init") → 连接成功
```

### 10.4 HTTP 请求层

`api.ts` 封装了所有 REST API 调用，`http.ts` 封装了底层 fetch + 错误处理。

`BASE_URL` 从 `.env` 文件读取，默认 `http://localhost:8080/api`。

### 10.5 Hooks

| Hook | 作用 |
|------|------|
| `useAgents` | 获取 Agent 列表，支持刷新 |
| `useChatSessions` | 获取会话列表，支持刷新 |
| `useDocuments` | 获取文档列表 |
| `useKnowledgeBases` | 获取知识库列表 |

---

## 11. AI 知识体系：这个项目用到了哪些 AI 概念

这一章帮你梳理项目涉及的所有 AI 知识点，面试时被问到任何方向都能接住。

### 11.1 Agent（智能体）核心概念

| 概念 | 项目中的体现 | 面试怎么讲 |
|------|------------|-----------|
| **Agent Loop** | `JChatMind.run()` 中的 for 循环 + step() | "Agent 的本质是一个循环：Think-Execute，直到 LLM 判断任务完成或到达安全上限" |
| **ReAct 模式** | think() = Reasoning, execute() = Acting | "我们实现了 ReAct（Reasoning + Acting）模式，这是学术界最主流的 Agent 架构之一" |
| **Tool Calling** | @Tool 注解 + ToolCallingManager | "LLM 不直接执行工具，而是输出 tool_calls JSON，由框架层解析并执行" |
| **Function Calling** | Spring AI 的 ChatClient + ToolCallback | "这是 OpenAI/DeepSeek 等模型提供的能力——让 LLM 能'声明'它想调用什么函数" |
| **状态机** | AgentState 枚举 | "Agent 有明确的状态转换：IDLE → FINISHED/ERROR，配合 MAX_STEPS 做安全兜底" |
| **滑动窗口记忆** | MessageWindowChatMemory(maxMessages=20) | "对话历史太多会超上下文窗口，用滑动窗口只保留最近 20 条" |

### 11.2 RAG（检索增强生成）

| 概念 | 项目中的体现 | 面试怎么讲 |
|------|------------|-----------|
| **RAG** | KnowledgeTool + RagService | "RAG = 先检索（Retrieval）再生成（Augmented Generation）。检索相关文档片段，作为上下文传给 LLM" |
| **Embedding** | Ollama(bge-m3) 生成 1024 维向量 | "Embedding 是把文本转为高维向量的过程，语义相似的文本在向量空间中距离更近" |
| **向量检索** | `ORDER BY embedding <-> vector LIMIT 3` | "用 pgvector 的距离运算符找最相似的向量，返回 top-3 结果" |
| **ivfflat 索引** | `USING ivfflat (embedding vector_l2_ops)` | "ivfflat 是倒排文件索引，先做 K-Means 聚类，查询时只搜最近的几个簇" |
| **分块策略** | 按 Markdown 标题分块 | "分块粒度直接影响检索质量——太粗混入噪声，太细丢失上下文" |
| **距离函数** | `<->` = 欧氏距离 | "还有余弦距离 `<=>` 和内积 `<#>`，bge-m3 通常用余弦距离效果最好" |

### 11.3 Prompt Engineering

| 概念 | 项目中的体现 | 面试怎么讲 |
|------|------------|-----------|
| **System Prompt** | Agent 表的 system_prompt 字段 | "系统提示词定义 Agent 的人格和行为约束，通过 .system() 注入，不入 chatMemory" |
| **工具选择提示** | thinkToolRules 硬编码在 think() 中 | "指导 LLM 在什么场景下调什么工具——这是 Function Calling 的 Prompt 设计" |
| **上下文窗口管理** | 只取最后一条用户消息 + 之后的消息 | "控制传给 LLM 的上下文范围，防止工具重复调用" |
| **结果截断** | MAX_TOOL_RESPONSE_LENGTH = 300 | "工具返回可能很大，截断防止上下文膨胀" |

### 11.4 LLM 模型

| 概念 | 项目中的体现 | 面试怎么讲 |
|------|------------|-----------|
| **DeepSeek Chat** | `deepseek-chat` 模型 | "国内性价比最高的对话模型之一，支持 Function Calling" |
| **智谱 GLM-4.6** | `glm-4.6` 模型 | "另一款国内大模型，同样支持 Function Calling" |
| **ChatClient** | Spring AI 抽象 | "Spring AI 的 ChatClient 封装了不同模型的 API 差异，提供统一接口" |
| **Temperature/Top-P** | AgentDTO.ChatOptions | "控制生成的随机性，temperature 越高越随机，top_p 越小越保守" |

### 11.5 Spring AI 框架知识

| 概念 | 项目中的体现 | 为什么要了解 |
|------|------------|-------------|
| `ChatClient` | `chatClient.prompt().call()` | Spring AI 的核心 API，统一不同模型的调用方式 |
| `ChatMemory` | `MessageWindowChatMemory` | 管理对话上下文的滑动窗口 |
| `ToolCallback` | `MethodToolCallbackProvider` | 把 Java 方法转为 LLM 可调用的工具 |
| `ToolCallingManager` | `toolCallingManager.executeToolCalls()` | 管理工具执行流程（项目关闭了自动执行，改为手动） |
| `DefaultToolCallingChatOptions` | `internalToolExecutionEnabled(false)` | 关键配置：禁用自动工具执行 |
| `@Tool` 注解 | 每个工具方法上的注解 | 声明工具的名称、描述、参数 |

---

## 12. 已踩的坑与潜在风险

### 12.1 已修复的坑

| 坑 | 现象 | 原因 | 修复 |
|----|------|------|------|
| getName() 与 @Tool(name) 不一致 | 前端工具列表显示名 vs LLM 可调用名不同 | WeatherTools 的 getName() 返回 "weatherTool" 但 @Tool(name="queryWeather") | 统一名称 |
| 消息排序问题 | 恢复记忆后消息顺序混乱 | SQL 查询是 DESC，未反转为 ASC | `Collections.reverse(chatMessages)` |
| 空安全问题 | NPE | 某些字段可能为 null 未做判空 | 加 StringUtils.hasLength() 检查 |

### 12.2 当前已知问题

| 编号 | 问题 | 严重度 | 说明 |
|------|------|--------|------|
| S1 | API Key 硬编码在 application.yaml | 🔴 高危 | 应该用环境变量或密钥管理（Vault） |
| S2 | 邮箱授权码硬编码 | 🔴 高危 | 同上 |
| S3 | DataBaseTools SQL 注入风险 | 🟡 中危 | 只检查 `startsWith("SELECT")`，`SELECT; DROP TABLE` 可绕过 |
| S4 | thinkPrompt 硬编码在 Java | 🟡 中危 | 应该配置化或动态生成 |
| S5 | 无流式输出 | 🟡 中危 | LLM 返回是全量等待，不是流式 |
| S6 | SSE 无心跳 | 🟡 中危 | Nginx 等代理 60-120s 无数据会断连 |
| S7 | thinkPrompt 中的工具规则不够灵活 | 🟢 低 | 应该根据 Agent 配置的可用工具动态生成 |
| RAG1 | 只支持 Markdown 分块 | 🟢 低 | PDF/Word 需要额外解析器 |
| RAG2 | ivfflat lists=100 偏少 | 🟢 低 | 10 万条应该 ~317 |
| RAG3 | 只对标题做 embedding，不对内容做 | 🟢 低 | 检索时用户查询和标题语义可能不匹配 |

### 12.3 设计层面的取舍（不是 bug，但要知道）

| 取舍 | 当前选择 | 替代方案 | 为什么这么选 |
|------|---------|---------|-------------|
| 异步方式 | @Async + 内存事件 | RabbitMQ/Kafka | 简单，不需要额外中间件 |
| 向量数据库 | pgvector（在 PostgreSQL 中） | Milvus/Pinecone | 运维简单，数据量在 pgvector 能力范围内 |
| Agent 每次新建实例 | Factory.create() 每次都 new | 缓存 Agent 实例 | Agent 配置可能随时变，每次都重新加载更安全 |
| 工具结果截断 | 硬编码 300 字符 | 按工具类型配置截断长度 | 简单够用 |
| 按标题分块 | 只遍历顶层节点 | 递归遍历所有级别标题 | 避免过度切分 |

---

## 13. 竞争力评估：这个项目够格吗？

### 13.1 结论：**够格实习，有竞争力**

原因：

1. **完整度高**：从 Agent Loop → 工具系统 → RAG → 多模型 → SSE → 前后端，覆盖了 AI 应用工程师的核心技能栈
2. **不是玩具项目**：有状态机、异常处理、分层架构、数据库设计，是工程化的代码，不是 demo
3. **AI 知识覆盖全面**：Agent、RAG、Function Calling、Embedding、Prompt Engineering 全都涉及
4. **能讲出设计思想**：不是"我调了个 API"，而是"我设计了 Agent 的循环架构"、"我实现了可扩展的工具框架"

### 13.2 对标 AI 应用工程师实习岗位要求

| 常见要求 | 项目覆盖度 | 说明 |
|---------|-----------|------|
| 理解 LLM 原理和 API 调用 | ✅ | DeepSeek + 智谱双模型，理解 ChatClient 接口 |
| RAG 检索增强 | ✅ | 完整链路：文档解析 → 分块 → Embedding → 向量检索 |
| Agent / Tool Calling | ✅ | Think-Execute 循环 + 框架化工具系统 |
| Prompt Engineering | ✅ | 系统提示词设计、工具选择规则、上下文管理 |
| Java / Spring Boot | ✅ | 完整的分层架构 + MyBatis + REST API |
| 数据库设计 | ✅ | PostgreSQL + JSONB + pgvector |
| 前端能力 | ✅ | React + TypeScript + SSE 实时通信 |
| 工程化能力 | ✅ | 设计模式、异常处理、分层架构、代码规范 |

### 13.3 与竞品对比

| 项目 | JChatMind 的优势 | JChatMind 的不足 |
|------|-----------------|-----------------|
| **LangChain 示例项目** | Java 生态（面试官更看重）、完整前后端、Agent 有状态管理 | 生态不如 LangChain 丰富 |
| **AutoGPT** | 有 Web 界面、可控的工具系统 | 复杂度不如 AutoGPT |
| **纯聊天 Demo** | 是 Agent 不是聊天、有 RAG、有工具系统 | — |
| **实习生的其他项目** | AI 知识覆盖全面、能讲 30 分钟不重复 | 如果只是 CRUD 项目会被秒杀 |

### 13.4 面试官可能会觉得不够的地方

1. **没有流式输出** — 现在是全量返回，用户要等 Agent 全部执行完才能看到结果
2. **没有对话记忆持久化方案** — Agent 每次新建实例重新加载，没有持久化的向量记忆
3. **没有评测系统** — RAG 检索质量没有量化指标（Recall@K、MRR）
4. **单机部署** — 没有集群、负载均衡、容灾方案
5. **没有 MCP 协议** — 当前热门的 Model Context Protocol 没有涉及

---

## 14. 优化路线图：怎么让它从"能用"到"能打"

### 14.1 P0（立即可做，效果立竿见影）

| 优化 | 工作量 | 收益 | 怎么讲 |
|------|--------|------|--------|
| **API Key 移到环境变量** | 30 分钟 | 修复安全问题 | "安全是基本功，密钥不能硬编码" |
| **SSE 心跳机制** | 1 小时 | 生产级稳定性 | "Nginx 60s 超时，加 keepalive 防断连" |
| **thinkPrompt 动态生成** | 2 小时 | 架构优化 | "根据 Agent 配置的工具列表自动拼装规则，不硬编码" |
| **后端发送 AI_THINKING/AI_EXECUTING 状态** | 1 小时 | 用户体验提升 | "用户能实时看到 Agent 在做什么" |
| **DataBaseTools 安全加固** | 1 小时 | 修复 SQL 注入 | "只读账号 + JSqlParser AST 白名单校验" |

### 14.2 P1（需要一些投入，但能显著提升竞争力）

| 优化 | 工作量 | 收益 | 怎么讲 |
|------|--------|------|--------|
| **流式输出（SSE Streaming）** | 1-2 天 | 用户体验质变 | "LLM 的 token 逐字输出，用户不需要等" |
| **RAG 混合检索** | 2-3 天 | 检索质量提升 | "向量相似度 + BM25 关键词匹配，互补召回" |
| **工具结果结构化返回** | 半天 | LLM 理解更好 | "返回 JSON 而非纯字符串，LLM 能更准确解析" |
| **消息队列替代 @Async** | 2 天 | 可靠性提升 | "RabbitMQ + 死信队列，消息不丢" |
| **重叠分块策略** | 半天 | RAG 质量提升 | "相邻块重叠 15%，防止信息断裂" |

### 14.3 P2（锦上添花，可以面试时提"下一步计划"）

| 优化 | 工作量 | 收益 |
|------|--------|------|
| **MCP 协议集成** | 3-5 天 | 跟上行业趋势 |
| **Agent 记忆系统** | 3-5 天 | 长期记忆 + 用户偏好 |
| **RAG 评估系统** | 2-3 天 | Recall@K / MRR 量化指标 |
| **多模态支持** | 3-5 天 | 图片/音频理解 |
| **Agent 编排（多 Agent 协作）** | 5+ 天 | 架构能力体现 |
| **Docker + K8s 部署** | 1-2 天 | 生产级部署 |

### 14.4 我建议你优先做的三件事

1. **流式输出** — 面试官第一个问题一定是"有没有流式输出"，没有会减分
2. **API Key 外置 + 安全加固** — 体现你的安全意识
3. **thinkPrompt 动态化** — 体现你的架构思维（从硬编码到配置化）

做完这三个，面试时能讲的内容直接翻倍。

---

## 15. 面试叙事：怎么讲这个项目最出彩

### 15.1 30 秒自我介绍版本

> "我做了一个 AI Agent 系统 JChatMind，基于 Spring AI + React。和普通聊天项目不同，它实现了 Think-Execute 自主决策循环——用户发消息后，Agent 能自己决定要不要调工具、调哪个、什么时候结束。技术上我设计了可扩展的工具框架（FIXED/OPTIONAL 双模式）、RAG 知识库检索（Markdown 解析 → Embedding → pgvector 向量检索）、多模型注册表（DeepSeek/智谱可切换），以及 SSE 实时推送 Agent 执行状态。"

### 15.2 技术亮点叙事（按面试官兴趣排序）

**亮点 1：Agent Loop 架构（必讲）**
- "不是调一次 API 就结束，而是自主决策循环"
- "我关闭了 Spring AI 的自动工具执行（internalToolExecutionEnabled=false），手动控制 Think-Execute 两阶段，这样才能在每一步做持久化和 SSE 推送"
- "有三种终止条件：LLM 自然结束、terminate 工具主动结束、MAX_STEPS 安全兜底"

**亮点 2：工具系统设计（必讲）**
- "新增工具只需实现 Tool 接口 + @Component，不需要改任何核心代码"
- "FIXED/OPTIONAL 双模式：系统级工具对所有 Agent 可用，业务级工具按需配置"

**亮点 3：RAG 全链路（推荐讲）**
- "不只是调 embedding API，还做了文档解析、分块策略、向量索引优化"
- "选 pgvector 的理由：和业务数据库合一，运维成本低，事务一致性好"

**亮点 4：事件驱动架构（加分项）**
- "Controller 只做持久化 + 发事件，不阻塞 HTTP 线程"
- "@Async 异步执行 Agent，Tomcat 线程池不受影响"
- "先持久化再发事件，经典的最终一致性模式"

### 5.3 高频面试问题速查

| 问题 | 核心回答 | 详细参见 |
|------|---------|---------|
| "这个项目和聊天机器人有什么区别？" | Agent 有自主决策能力，能多步推理调用工具 | 第 1 章 |
| "请求的完整链路是怎样的？" | Controller → Facade → Event → Factory → Agent Loop → SSE | 第 2 章 + Q1 |
| "为什么用事件驱动？" | 解耦 + 不阻塞 HTTP 线程 | 第 3 章 + Q2 |
| "Agent Loop 怎么工作的？" | Think-Execute 循环，最多 20 步 | 第 4 章 + Q4 |
| "为什么要关 auto tool execution？" | 要在每一步做持久化和 SSE 推送 | 第 4 章 + Q4 |
| "工具系统怎么扩展？" | 实现 Tool + @Component，零核心侵入 | 第 5 章 + Q7 |
| "RAG 的完整流程？" | 解析 → 分块 → Embedding → 向量检索 | 第 6 章 + Q11 |
| "为什么选 pgvector？" | 与业务数据库合一，运维简单 | 第 6 章 + Q13 |
| "SSE 和 WebSocket 怎么选？" | 单向推送选 SSE，双向交互选 WebSocket | 第 7 章 + Q16 |
| "项目有什么不足？下一步做什么？" | 无流式输出、API Key 硬编码、单机部署 | 第 12 + 14 章 |

### 15.4 简历写法

```
项目名称：JChatMind — AI Agent 智能助手系统
技术栈：Java 17 / Spring Boot 3.5 / Spring AI 1.1 / React 19 / PostgreSQL + pgvector / Ollama
项目时间：2024.12 - 2025.05

项目描述：
  基于 Spring AI 构建的 AI Agent 系统，实现 Think-Execute 自主决策循环，
  支持多步推理、工具调用、RAG 知识库检索，SSE 实时推送执行状态。

核心工作：
  · 设计并实现 Agent Loop 架构（Think-Execute 循环 + 状态机 + 三重终止条件），
    手动接管 Spring AI 的工具执行流程，实现消息持久化与 SSE 推送的精细化控制
  · 构建 FIXED/OPTIONAL 双模式工具框架，新增工具零核心代码侵入，
    通过 @Component 自动注册 + ToolType 分类管理
  · 完成 RAG 全链路实现：Flexmark Markdown 解析 → 标题分块 → Ollama(bge-m3) 
    Embedding → pgvector ivfflat 向量索引 → 余弦相似度检索
  · 采用注册表模式管理多模型（DeepSeek / 智谱），新增模型仅需 3 行配置
  · 基于 SSE + ConcurrentHashMap 实现 Agent 执行状态实时推送，
    前端通过 EventSource 接收 THINKING / EXECUTING / DONE 状态变更

技术亮点：
  · 事件驱动架构：Spring ApplicationEvent + @Async 异步解耦，
    Controller 返回 HTTP 200 后 Agent 在后台线程池执行
  · 工具返回结果截断机制（300 字符上限），防止上下文窗口膨胀干扰 LLM 决策
  · 自定义 PgVectorTypeHandler 解决 MyBatis 无法映射 PostgreSQL 扩展类型的问题
```

### 15.5 最后：面试心态

**你不需要知道所有答案。** 面试官更看重的是：
1. 你能不能把**整体架构讲清楚**（5 分钟内不卡壳）
2. 你能不能解释**为什么这么设计**（不是背答案，是有思考）
3. 你能不能指出**不足和改进方向**（体现成长性）
4. 你能不能**在追问中展开细节**（证明你真的做过）

这个项目的深度和广度在实习生中已经算上游。把第 1-4 章的全局叙事练熟，再对照 Q&A 文档把细节补上，面试时底气会很足。

---

> **文档版本：** v1.0
> **最后更新：** 2026-05-27
> **配套文档：** `学习笔记_JChatMind系统掌握.md`（Q&A 问答库）