# JChatMind 项目问答库 — AI应用工程师面试备战

> 目标：从"会用"到"能讲清楚为什么"
>
> 每个问题从四个维度拆解：**作用** → **原因** → **替代** → **优化**
>
> 再附**分析与切入方式**：考点定位、回答思路、查漏补缺、进阶加分

---

## 目录

1. [第一阶段：架构全局](#第一阶段架构全局)
2. [第二阶段：Agent 核心](#第二阶段agent核心)
3. [第三阶段：工具系统](#第三阶段工具系统)
4. [第四阶段：RAG 知识库](#第四阶段rag知识库)
5. [第五阶段：SSE 实时通信](#第五阶段sse实时通信)
6. [第六阶段：多模型注册表](#第六阶段多模型注册表)
7. [第七阶段：数据模型与分层设计](#第七阶段数据模型与分层设计)
8. [第八阶段：安全与优化](#第八阶段安全与优化)
9. [面试备战索引](#面试备战索引)

---

## 第一阶段：架构全局

```
POST /api/chat-messages
  → ChatMessageController → ChatMessageFacadeService (持久化 + 发布事件)
  → @Async ChatEventListener → JChatMindFactory.create() → JChatMind.run()
  → Think-Execute 循环 → 通过 SseService 实时推送到前端
```

---

### Q1：用户发消息的完整链路

| 维度 | 内容 |
|------|------|
| **作用** | 描述一条用户消息从浏览器发送到 Agent 响应完成，经过的所有后端组件 |
| **原因** | 采用事件驱动架构解耦"接收请求"和"执行业务"：Controller 只做持久化 + 发事件，不阻塞；Agent 异步执行，全程 SSE 推送状态 |
| **替代** | 同步调用（Controller 里直接 new JChatMind().run()）→ 10-30s 占用 Tomcat 线程，高并发下线程池耗尽 |
| **优化** | 引入消息队列（RabbitMQ/Kafka）提升可靠性 + 死信队列处理失败消息 + 分布式追踪（SkyWalking）串联全链路 |

**你的回答与反思**：
- **你的回答**：controller → service → eventlistener → agent（方向对，细节不够）
- **评分**：⭐⭐⭐✩✩ (3/5)
- **不足**：只说了组件名，漏掉了：Factory 装配阶段（loadMemory/resolveTools/resolveKnowledgeBases）、@Async 异步机制、SSE 推送、ChatEvent 事件
- **改进**：先一句话概括"先存消息再异步处理"，再分层展开，最后点关键设计

**分析与切入方式**：
- **核心考点**：事件驱动架构 + 全链路思维。面试官看你能不能从"发消息"讲到"Agent 出结果"
- **回答思路**：分层展开（Controller → Event → Factory → Agent Loop → SSE），点出关键设计（先持久化再发事件、@Async 线程池隔离）
- **查漏补缺**：容易漏 Factory 装配阶段和 SSE 推送。这不是简单的链式调用，中间有 @Async 线程池切换
- **面试加分**：指出这是"最终一致性"设计——Controller 返回 200 时 Agent 还没执行，用户靠 SSE 感知进度

---

### Q2：为什么用事件驱动而不是直接调 Agent？

| 维度 | 内容 |
|------|------|
| **作用** | 将"接收请求"和"处理业务"拆成两个阶段，通过 ApplicationEvent + @Async 异步执行 |
| **原因** | 1. **解耦**：Controller 不需要知道 Agent 怎么处理、用什么模型、调什么工具。2. **不阻塞 HTTP 线程**：Agent 可能耗时 10-30 秒，同步调用会占满 Tomcat 线程池 |
| **替代** | ① 同步调用（最简单但不可控）② RabbitMQ/Kafka（更可靠但引入中间件成本）③ CompletableFuture（轻量但需自己管理线程池） |
| **优化** | 可加死信队列兜底失败消息、重试机制（Spring Retry）、@Async 线程池监控告警（线程池满时拒绝策略） |

**你的回答与反思**：
- **你的回答**：先保证用户消息持久化；减少信息丢失；避免 agent 被突然调用占用缓存
- **评分**：⭐⭐⭐✩✩ (3/5)
- **不足**：方向对，但少了核心理解：**解耦（关注点分离）**和**不阻塞 HTTP 线程**。你说的"缓存"逻辑不准确
- **改进**：拆两个层面答：① 功能解耦（Controller 只管存消息+通知）② 线程解耦（Agent 10-30s 执行不占 Tomcat 线程）

**分析与切入方式**：
- **核心考点**："解耦"不止接口分层，还有**执行线程的解耦**
- **回答思路**：先摆两个核心原因（功能解耦 + 线程不阻塞），再展开每层的收益，最后举反例（同步调用 = Tomcat 线程池耗尽）
- **查漏补缺**：只答"减少消息丢失"不够——那只是附带好处，不是核心设计动机
- **面试加分**：说出 @Async 线程池参数（core=4, max=10, queue=100）+ 拒绝策略 + 对比 MQ 方案优劣

---

## 第二阶段：Agent 核心

```
JChatMind.run()
  → for i in 0..MAX_STEPS:
    → step()
      → think(): 调 LLM → 获取 tool_calls 决策
      → execute(): 执行工具 → 持久化 → SSE → 更新 chatMemory
    → 直到: 无 tool_calls / 调 terminate / 超 MAX_STEPS
```

---

### Q3：thinkPrompt 为什么用 `.system()` 注入？

| 维度 | 内容 |
|------|------|
| **作用** | 将工具选择规则以系统级提示词传给 LLM，不混入对话记忆 |
| **原因** | ① **窗口配额**：MessageWindowChatMemory maxMessages=20，塞进去每轮吃掉一个槽位 ② **优先级稀释**：.system() 有系统级约束力，当普通消息发可能被忽略 ③ **冗余累积**：每次 think() 生成新 prompt（知识库可变），旧的不删就重复堆砌 |
| **替代** | 直接 chatMemory.add(new SystemMessage(thinkPrompt)) → 撑爆 20 条窗口 / 优先级被稀释 / 旧版本残留 |
| **优化** | 动态生成 thinkPrompt：根据 Agent 配置的可用工具列表自动拼装规则，不需要硬编码在 Java 代码里 |

**你的回答与反思**：
- **你的回答**：1. 防止上下文过长 2. 防止记忆污染 3. .system() 有系统优先级，加 chatMemory 变成普通消息失去约束力
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：漏了最致命的一点：**MessageWindowChatMemory 窗口配额**——maxMessages=20，每轮塞一条 thinkPrompt，5 轮后真正的对话被挤出去
- **改进**：加上窗口配额的角度：不仅污染记忆，还占宝贵的窗口槽位

**分析与切入方式**：
- **核心考点**：.system() vs chatMemory 的区别 + 滑动窗口机制
- **回答思路**：三个层面——① 窗口配额 ② 优先级稀释 ③ 冗余累积。每层举一个具体例子
- **查漏补缺**：容易只答"记忆污染"漏掉窗口配额。20 条窗口，Agent 循环 5 轮占 1/4
- **面试加分**：联系 Token 计费——多余的 thinkPrompt 不仅占窗口还浪费钱。算出 5 轮循环的额外 Token

---

### Q4：为什么要关 internalToolExecutionEnabled？

| 维度 | 内容 |
|------|------|
| **作用** | 关闭 Spring AI 默认的自动工具执行，改为手动控制 Think-Execute 两阶段循环 |
| **原因** | 默认模式（true）下，整个"调 LLM → 执行工具 → 结果放回 → 再调 LLM → ..."在一个 call() 内部完成，开发者无法插入持久化、SSE 推送、循环控制、错误处理 |
| **替代** | ① 默认 true（失去控制权，但代码简单）② 完全自己实现 ToolCallingManager（不必要，Spring AI 的工具调用管理功能仍可用） |
| **优化** | 可考虑"混合模式"：简单确定性工具（如 terminate）让 Spring AI 自动执行，复杂外部工具（如 DataBase/Email）手动控制 |

**你的回答与反思**：
- **你的回答**：不关掉 LLM 自动调工具并放回结果再调 LLM 返回全部结果。关掉后 think() 只获取 tool_call，execute() 真正执行，每一步可控、可持久化、可 SSE
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：漏了关键对比：不关掉时整个循环在 call() 内部完成，**开发者无法介入**。不是"自动调了", 是"开发者根本没有机会做持久化和 SSE"
- **改进**：强调"控制权"——关掉后才能：saveMessage、SSE 推送、MAX_STEPS 检查、terminate 检查

**分析与切入方式**：
- **核心考点**：Spring AI 的 ToolCallingManager 机制 + Agent 系统的控制权设计
- **回答思路**：先解释默认模式做了什么（call() 内部自动循环），再说明为什么需要控制权（持久化/SSE/MAX_STEPS/terminate），最后对比两种模式
- **查漏补缺**：别只说"为了控制流程"——要说具体失去了什么（消息不持久、前端看不到状态、无法限制循环、异常无法降级）
- **面试加分**：讲出源码实现——ToolCallingManager 本质是 call() 内部的 while 循环，关掉后我们在外部实现同样的逻辑但每一步可介入

---

### Q5：MAX_STEPS=20 到了会发生什么？

| 维度 | 内容 |
|------|------|
| **作用** | 防止 Agent 死循环的硬性安全上限 |
| **原因** | LLM 可能持续调用工具不终止（如反复查天气但忽略结果），需要安全阀强制结束 |
| **替代** | ① 无限循环（危险，Token 消耗失控）② 基于 Token 数截止（更精确但复杂）③ 基于时间截止（超时机制） |
| **优化** | ① **自适应步数**：按任务复杂度动态调整 ② **超步降级**：超过 MAX_STEPS 后切到"只能直接回答"模式 ③ **多模型分级**：简单问题用小模型快走，超出步数转大模型深度推理 ④ **上下文压缩**：长循环后摘要关键信息，替换原始上下文降本 |

**你的回答与反思**：
- **你的回答**：到了设 FINISHED 结束循环。改进：1. 上下文压缩防偏离 2. 多模型分阶段（小模型处理简单问题，超步转高级模型）3. 设终止变量防死循环
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：纠正一点：MAX_STEPS 到了**不会调 terminate**——terminate 是 execute() 检查工具名，MAX_STEPS 是 run() 循环条件跳出，两条独立路径
- **改进**：区分"被动安全阀（MAX_STEPS）"和"主动结束（terminate）"两个概念，不要混为一谈

**分析与切入方式**：
- **核心考点**：Agent 系统的安全性设计。面试官想看你有没有考虑到"LLM 不可靠，系统必须有兜底"
- **回答思路**：先说当前怎么做的（20 步硬上限），再分析为什么需要（LLM 不终止的 case），最后给改进方案（2-3 个有深度的想法）
- **查漏补缺**：容易混淆 MAX_STEPS 和 terminate——MAX_STEPS 是**被动安全阀**（不管当前状态直接结束），terminate 是**主动结束信号**（工具告知 LLM 决定结束）。两者独立
- **面试加分**：能说出"自适应步数 + 分级模型"的组合方案——把简单查询用小模型处理（步数少、成本低），复杂推理在超步后路由到大模型。这是开源项目（AutoGPT、LangChain）的成熟模式

---

### Q6：execute() 中工具调用抛出异常会怎样？

| 维度 | 内容 |
|------|------|
| **作用** | 处理工具执行失败时的异常传播路径 |
| **原因** | 外部依赖（天气 API、数据库、邮件服务器）可能不可用，需要区分"工具内部处理的异常"和"没 catch 住的异常" |
| **替代** | ① 所有工具 catch 所有异常（当前做法，但不统一）② 全局异常统一处理（AOP 切面） |
| **优化** | ① **工具级重试**：用 Spring RetryTemplate，对网络抖动自动重试 ② **熔断降级**：引入 Resilience4j，API 连续失败后快速熔断 ③ **兜底响应**：catch 异常后返回结构化错误而非纯字符串，LLM 能更好地决定下一步 |

**你的回答与反思**：
- **你的回答**：工具返回错误后 LLM 回答"无法连接工具"。改进：加最多 3 次重试
- **评分**：⭐⭐⭐✩✩ (3/5)
- **不足**：答的是**工具内部自己 catch 异常**的场景，不是 execute() 没 catch 住的异常。后者会直接抛到 run() 的 catch，agentState=ERROR，用户无任何响应
- **改进**：区分两层：① 工具内部 catch（返回错误字符串，LLM 决定下一步）② 框架层没 catch 住（抛到 run()，用户无响应）

**分析与切入方式**：
- **核心考点**：异常传播路径 + 分层异常处理思维。面试官想看你能否区分"工具内部异常"和"框架异常"
- **回答思路**：先明确两个层面——工具内部自己 catch（返回错误字符串，LLM 决定怎么办）vs execute() 没 catch 住的（直接抛到 run()，agentState=ERROR，用户无响应）。再分别展开影响
- **查漏补缺**：容易只答前者（工具返回错误消息）而忽略后者（框架异常导致用户无响应）。后者的影响更严重——用户完全不知道发生了什么
- **面试加分**：指出当前设计中"用户无响应"是最糟糕的体验，建议至少发一条 SSE 消息（"AI 处理异常，请重试"）。能引入 Spring 的 @Async 异常处理（AsyncUncaughtExceptionHandler）来统一处理

---

## 第三阶段：工具系统

```
Tool 接口:
  getName() / getDescription() / getType() → FIXED | OPTIONAL

注册: @Component → Spring 自动注入到 ToolFacadeServiceImpl 的 List<Tool>
匹配: resolveRuntimeTools() = 全部 FIXED + DB allowed_tools 匹配的 OPTIONAL
```

---

### Q7：新增一个工具要改哪些代码？

| 维度 | 内容 |
|------|------|
| **作用** | 验证工具系统的可扩展性设计——新增工具是否需要改核心代码 |
| **原因** | 通过 Tool 接口 + @Component 自动注入 + FIXED/OPTIONAL 双模式，实现"新增 0 核心侵入" |
| **替代** | ① 硬编码工具列表（每增一个改核心代码）② 配置文件声明（灵活性不如注解注入） |
| **优化** | ① 运行时动态注册/卸载工具（通过管理端 API）② 工具版本管理（同名工具多版本共存）③ 工具权限组（按角色/Access Key 控制哪些工具可用） |

**你的回答与反思**：
- **你的回答**：新建 Tool 类实现 Tool 接口，加 @Component 和 @Tool 注解，Spring 自动扫描到 List<Tool> 中
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：漏了两个细节：① OPTIONAL 工具需要在 DB Agent 表的 allowed_tools 字段加工具名 ② getName() 必须与 @Tool(name) 一致（WeatherTools 的坑）
- **改进**：分 FIXED/OPTIONAL 两种情况说明：FIXED 只需注解注入，OPTIONAL 还需要 DB 配置

**分析与切入方式**：
- **核心考点**：可扩展性设计 + Spring 自动注入的理解
- **回答思路**：分步骤说明——新建类实现 Tool 接口 → @Component → @Tool 注解 → 如果是 OPTIONAL 还要在 DB 配置。最后强调"不需要改 JChatMind.java 或 Factory"
- **查漏补缺**：容易忘记 getName() 和 @Tool(name) 必须一致（我们刚修过 WeatherTools 的坑），以及 OPTIONAL 工具需要额外数据库配置
- **面试加分**：指出 getName() 与 @Tool(name) 不一致是设计瑕疵——应该统一使用一个来源（如 getName()），避免两处配置。Spring 的 BeanPostProcessor 可以自动校验两者一致性

---

### Q8：FIXED 和 OPTIONAL 的区别在代码中如何实现？

| 维度 | 内容 |
|------|------|
| **作用** | 区分系统强制工具和按需配置的可选工具 |
| **原因** | 某些工具（KnowledgeTool、TerminateTool）应该对所有 Agent 可用；某些（DataBase、Email）需要按 Agent 需求配置 |
| **替代** | ① 全部 FIXED（丢失灵活性，所有 Agent 都有不需要的工具）② 全部 OPTIONAL（基础功能可能缺失，每个 Agent 都要手动配） |
| **优化** | ① 工具分类/标签（"基础"、"数据库"、"通信"），按标签批量授权 ② 按角色自动匹配（管理员自动获得运维类工具） |

**你的回答与反思**：
- **你的回答**：通过 tool.getType().equals(ToolType.XXX) 过滤，FIXED 全部加入，OPTIONAL 只加入选中的
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：正确但不够精确。精确说法：resolveRuntimeTools() = 全部 FIXED + DB allowed_tools 匹配的 OPTIONAL。Agent 看到的是两者的**并集**
- **改进**：把"全部 FIXED + 匹配的 OPTIONAL"这个公式讲清楚，体现对 resolveRuntimeTools() 源码的理解

**分析与切入方式**：
- **核心考点**：是否理解 FIXED/OPTIONAL 模式对应的业务需求——系统级 vs 用户级
- **回答思路**：从业务需求出发（"有些工具必须对所有 Agent 生效，有些需要按需授权"），再到源码实现（ToolType 枚举 → ToolFacadeServiceImpl.filter() → Factory.resolveRuntimeTools()）
- **查漏补缺**：记得说出"并集"——Agent 最终看到的工具是 FIXED + 匹配的 OPTIONAL，不是二选一
- **面试加分**：类比 Linux 权限模型（755 中的 owner/group/other），说明"工具权限"设计可以借鉴分层思路

---

### Q9：DataBaseTools 的 SQL 注入风险？

| 维度 | 内容 |
|------|------|
| **作用** | LLM 生成的 SQL 直接执行，带来注入风险 |
| **原因** | 为了灵活性直接让 LLM 写 SQL，但 SQL 来自不可信来源（LLM 可能被 prompt injection 诱导生成恶意 SQL） |
| **替代** | ① 只读数据库账号（最有效，即使注入也无法写/删）② SQL parser AST 白名单（JSqlParser）③ 预定义查询模板（LLM 只填参数，不生成完整 SQL） |
| **优化** | 多层防御：**网络层**→ Agent 服务与数据库网络隔离 **权限层**→ 只读账号 **输入层**→ JSqlParser 校验 **监控层**→ 慢查询/异常查询告警 |

**你的回答与反思**：
- **你的回答**：只允许 SELECT 但 `SELECT; DROP` 等多语句可绕过。建议用 JdbcTemplate
- **评分**：⭐⭐⭐⭐✩ (4/5)
- **不足**：纠正：项目**已经用了 JdbcTemplate**。问题不在"用不用 JdbcTemplate"，在传参方式——`jdbcTemplate.query(String sql, ...)` 传原始字符串，等价于 Statement.executeQuery()
- **改进**：建议改为：① 只读数据库账号（最根本）② JSqlParser AST 白名单校验 ③ 过滤特殊字符（; -- /* */）

**分析与切入方式**：
- **核心考点**：AI 系统的安全风险意识。LLM 生成的代码/查询直接执行是 AI 应用最常见的攻击面
- **回答思路**：先指出现有问题（只检查 startsWith("SELECT")，可被多语句绕过），再给分层防御方案（权限隔离 > 输入校验 > 监控告警）
- **查漏补缺**：容易只想到输入过滤，忽略"只读账号"这种更根本的解决方案。SQL 注入的防御一定要从底层做起
- **面试加分**：能联系 LLM 特有的风险——**Prompt Injection**（用户诱导 LLM 生成恶意 SQL）和**间接 Prompt Injection**（知识库文档中注入恶意指令）。这是 AI 安全领域的热门话题

---

### Q10：TerminateTool 是 void 返回，怎么让 Agent 结束？

| 维度 | 内容 |
|------|------|
| **作用** | Agent 通过 terminate 工具主动告知系统"任务完成，结束循环" |
| **原因** | void 返回后 Spring AI 自动包装成 ToolResponse(name="terminate", responseData="")，execute() 中通过 resp.name().equals("terminate") 匹配命中来终止 |
| **替代** | ① 返回特殊字符串（不可靠，依赖 LLM 理解）② 抛出特定异常（过于粗暴）③ 框架级别检查（当前做法，干净） |
| **优化** | ① 确认步骤：terminate 前加一次 LLM 确认，防止误终止 ② 强制终止条件：即使 LLM 没调 terminate，MAX_STEPS 到了也能兜底 |

**你的回答与反思**：
- **你的回答**：返回设置 agent.FINISHED 状态，下一轮检查到 FINISHED 退出
- **评分**：⭐⭐⭐✩✩ (3/5)
- **不足**：没回答核心问题：**void 没有返回值**，它怎么触发终止的？关键机制是 Spring AI 把 void 包装成 ToolResponse(name="terminate")，execute() 靠工具名匹配，不是靠返回值
- **改进**：先说 Spring AI 对 void 的包装机制，再说 execute() 中的工具名匹配逻辑

**分析与切入方式**：
- **核心考点**：Spring AI 的 @Tool 返回值处理机制 + Agent 终止条件
- **回答思路**：关键点在于——终止不靠返回值内容，靠 @Tool(name="terminate") 的工具名匹配。Spring AI 对任何返回值（包括 void）都包装成 ToolResponse
- **查漏补缺**：容易说"返回 FINISHED 状态"——terminate 不直接返回状态，而是 execute() 里检查工具名后设置 agentState
- **面试加分**：对比 LangChain 的 AgentFinish 机制——LangChain 是工具返回特殊对象，Spring AI 通过工具名匹配，本质都是"框架层识别终止信号"。两种模式各有优劣，可以讨论

---

## 第四阶段：RAG 知识库

```
上传: flexmark 解析 Markdown → 按标题分块 → bge-m3 embedding → 存入 chunk_bge_m3 表
检索: 用户提问向量化 → ivfflat 索引相似搜索 → 返回 top-3
调用: KnowledgeTool.knowledgeQuery(kbsId, query) → Agent 获取结果
```

---

### Q11：文档上传→分块→存储的完整链路

| 维度 | 内容 |
|------|------|
| **作用** | 私有文档从上传到可被 LLM 语义检索的完整处理流程 |
| **原因** | LLM 训练数据不包含私有文档，需要通过 RAG（检索增强生成）让 LLM 能访问特定知识 |
| **替代** | ① Fine-tuning（成本高、更新慢、需要标注数据）② 纯 LLM 知识（无法覆盖私有数据）③ Graph RAG（知识图谱 + 向量混合检索，更精确但复杂度更高） |
| **优化** | ① **混合检索**：向量相似度 + BM25 关键词，互补召回 ② **重排序**：用 cross-encoder 对召回结果精排 ③ **多路召回**：分块 + 摘要 + 标题多路并行，合并去重 |

**你的回答与反思**：
- **你的回答**：flexmark 解析 Markdown → 按标题分块 → bge-m3 生成 1024 维 embedding → 存 chunk 表 → 用户提问时向量化 → 余弦相似度 → 返回 top3 → Agent 调 KnowledgeTool
- **评分**：⭐⭐⭐⭐⭐ (5/5)
- **不足**：无。全链路完整，上传端和检索端都覆盖了
- **改进**：继续保持

**分析与切入方式**：
- **核心考点**：RAG 全链路理解——不只是"embedding + 向量搜索"，还有文档解析、分块策略、存储、检索几个环节
- **回答思路**：分"写入端"和"读取端"两阶段描述。写入：解析 → 分块 → embedding → 存储；读取：查询 embedding → 向量搜索 → 返回 top-N
- **查漏补缺**：容易漏掉文档解析环节（flexmark Markdown 解析器），以及"分块策略"这个影响检索质量的关键点
- **面试加分**：能主动聊 RAG 的痛点——分块大小怎么选（256 vs 512 tokens）、上下文窗口怎么处理（多块合并是否超限）、检索不到怎么办（意图识别 + 改写查询）。这些是生产级 RAG 都会遇到的工程问题

---

### Q12：当前分块策略是什么？有什么缺点？

| 维度 | 内容 |
|------|------|
| **作用** | 将长文档按语义单元切分成适合检索的短片段 |
| **原因** | LLM 上下文窗口有限 + 向量检索需要短文本才能精确匹配语义 |
| **替代** | ① 固定 Token 数切分（简单但可能切断语义）② 语义切分（NLP 模型检测段落边界，更精确但慢）③ Agent 自主切分（LLM 决定在哪切，灵活但成本高） |
| **优化** | ① **重叠分块**：相邻块重叠 10-20% 防止信息断裂 ② **分层分块**：标题 → 段落 → 句子三级，检索时从粗到细 ③ **元数据注入**：块中保留文档名、章节标题，提升检索上下文 |

**分析与切入方式**：
- **核心考点**：是否理解分块策略对检索质量的决定性影响——这是 RAG 系统最关键的超参数之一
- **回答思路**：先说当前是什么（按 Markdown 标题分块），再说缺点（大标题下内容过长、语义可能割裂、不支持非标题分隔的文档），最后给改进方案
- **查漏补缺**：不要只说分块方式，要能说出"分块大小影响检索精度"——块太小丢失上下文，块太大混入噪声。这是经典的"分块粒度权衡"
- **面试加分**：引用 LangChain 的文本分割器（RecursiveCharacterTextSplitter、MarkdownHeaderTextSplitter）作为行业实践。能说出评估指标：Recall@K、MRR（平均倒数排名）

---

### Q13：为什么选 pgvector 不选独立向量数据库？

| 维度 | 内容 |
|------|------|
| **作用** | 在 PostgreSQL 中直接存储和检索向量，不引入新的中间件 |
| **原因** | ① 减少运维复杂度（不引入 Milvus/Pinecone 等独立组件）② 利用 PostgreSQL 的事务、备份、权限体系 ③ 数据量在 pgvector 适用范围内（百万级以内，ivfflat 索引足够） |
| **替代** | ① Milvus（专业向量数据库，适合十亿级）② Pinecone（托管服务，省心但贵）③ Elasticsearch（文本+向量混合，适合已有 ES 的团队） |
| **优化** | ① 数据量增长后升级到 HNSW 索引（查询更快但构建更慢）② 引入分层存储（热数据 pgvector、冷数据归档）③ 加监控（ivfflat 的 probes 参数调优） |

**分析与切入方式**：
- **核心考点**：技术选型思维——知道每种方案的优劣势，以及选择依据
- **回答思路**：先说选择 pgvector 的理由（与业务数据库合一、运维成本低、数据量适配），再说哪些场景应该换别的方案（十亿级→Milvus、已有 ES 基础设施→ES）
- **查漏补缺**：不要只说"pgvector 好"——要说清楚"什么情况下 pgvector 不够"。能给出量化阈值（百万级内 pgvector 够用，亿级上 HNSW 索引内存占用过高）
- **面试加分**：对比 ivfflat 和 HNSW 的性能差异——ivfflat 构建快但查询慢（适合写多读少），HNSW 查询快但构建慢（适合读多写少）。能根据项目场景选择

---

### Q14：`embedding <->` 是什么运算符？还有其他选项吗？

| 维度 | 内容 |
|------|------|
| **作用** | pgvector 中计算两个向量的距离/相似度运算符 |
| **原因** | <-> 是欧氏距离（L2），还有 <=>（余弦距离）和 <#>（内积距离）。项目用了余弦距离（<=>）还是欧氏距离需要看具体 SQL |
| **替代** | ① <=> 余弦距离（通常对 embedding 效果最好，因为 bge-m3 的 embedding 已归一化时余弦等价于内积）② <#> 内积距离（当向量已归一化时与余弦等价，计算更快） |
| **优化** | ① 根据 embedding 模型选择匹配的距离函数 ② 使用 ivfflat 索引需要指定距离类型（vector_cosine_ops / vector_l2_ops）③ 索引的 probes 参数调优（默认 1，一般设 10-100） |

**分析与切入方式**：
- **核心考点**：向量距离函数的基本知识——不是"知道有这几种"就行，还要知道"分别什么时候用"
- **回答思路**：先列出三种运算符及数学含义，然后说选择依据（bge-m3 的 embedding 通常用余弦距离），最后说索引怎么选（cosine_ops / l2_ops）
- **查漏补缺**：容易混淆"余弦相似度"（值越大越相似，范围 [-1,1]）和"余弦距离"（1 - 余弦相似度，值越小越相似）。pgvector 的 <=> 是余弦距离
- **面试加分**：能深入说——当 embedding 经过 L2 归一化后，内积和余弦等价。所以许多场景用 <#> 代替 <=> 以获得更快速度

---

### Q15：10 万条 chunk，ivfflat 的 `lists=100` 合理吗？

| 维度 | 内容 |
|------|------|
| **作用** | ivfflat 索引的 lists 参数控制聚类数，直接影响召回率和查询速度 |
| **原因** | 经验公式：lists = sqrt(rows) ≈ 317（10万条）。lists=100 意味着每簇约 1000 条，查询时需要扫描的簇较多（probes 要设大才能保证召回），lists 偏少 |
| **替代** | ① lists = sqrt(rows) ≈ 317（推荐）② lists = rows / 1000 = 100（当前，偏少）③ 数据量更大时换 HNSW 索引 |
| **优化** | ① 重建索引：ALTER INDEX ... REBUILD WITH (lists = 300) ② probes 调优：SET ivfflat.probes = 10~50（越大召回越高但越慢）③ 换 HNSW 索引：构建慢但查询快，适合读多写少 |

**分析与切入方式**：
- **核心考点**：向量索引的参数理解和调优能力——这是生产级 RAG 的工程化能力体现
- **回答思路**：先给结论（lists=100 偏低），再用公式说明理由（sqrt(100000) ≈ 317），最后给出调优方案和 probes 搭配
- **查漏补缺**：容易只答"不合理"说不出具体数字原因。记住 sqrt(N) 这个经验公式
- **面试加分**：能说 lists 和 probes 的 trade-off——lists 越大每簇越小（查询快），但 probes 要相应增大（要查更多簇才能保证召回）。这是一对需要根据实际数据分布调试的参数。能建议 A/B 测试方法

---

## 第五阶段：SSE 实时通信

```
SseEmitter 长连接 → ConcurrentHashMap<String, SseEmitter> 管理
前端 EventSource 接收 → 消息类型: PLANNING / THINKING / EXECUTING / GENERATED_CONTENT / DONE
```

---

### Q16：SSE 和 WebSocket 的区别？为什么选 SSE？

| 维度 | 内容 |
|------|------|
| **作用** | 从服务器向客户端单向推送 Agent 执行状态的实时通信协议 |
| **原因** | SSE 天然支持单向推送（服务器→客户端），JavaScript 原生 EventSource API 无需额外库，自动断线重连 |
| **替代** | ① WebSocket（全双工，但本项目不需要客户端→服务器的实时通信，复杂度过高）② 轮询（简单但延迟高、浪费资源）③ 长轮询（兼容性好但实现复杂） |
| **优化** | ① 加心跳（SSE 默认 30 分钟超时，加每 30s 发送 keepalive）② 断线重连策略（EventSource 自动重连，但可加指数退避）③ 连接数限制（ConcurrentHashMap 做容量控制，超限时拒绝新连接） |

**分析与切入方式**：
- **核心考点**：通信协议选型——不是"知道 SSE 和 WebSocket"，而是"知道为什么在这个场景选 SSE"
- **回答思路**：先分析场景需求（单向推送、不需要客户端上行实时通信），再对比各方案优劣（SSE 最适合这个场景）
- **查漏补缺**：容易只说"SSE 比 WebSocket 轻量"——要说出具体理由：① 浏览器原生支持，不用装库 ② 自动重连 ③ 基于 HTTP，兼容性好
- **面试加分**：能说出 SSE 的局限——只支持文本（WebSocket 支持二进制）、浏览器限制同时 6 个 SSE 连接、IE 不支持。如果场景变成双向实时通信（如协同编辑），应该换 WebSocket

---

### Q17：SseServiceImpl 用 ConcurrentHashMap 管理连接，并发安全吗？

| 维度 | 内容 |
|------|------|
| **作用** | 存储 sessionId → SseEmitter 的映射，支持高并发下的连接管理 |
| **原因** | ConcurrentHashMap 的 put/get/remove 是线程安全的，多个请求同时建立/关闭连接不会出现数据竞争 |
| **替代** | ① synchronized Map（性能差，全表锁）② 读写锁（ReentrantReadWriteLock，过度设计）③ 无锁实现（如 CopyOnWriteArrayList，不适合频繁增删） |
| **优化** | ① 连接超时自动清理（SseEmitter.onCompletion / onTimeout 回调中 remove）② 加容量限制（防止内存泄漏）③ 连接数监控告警（仪表盘展示当前连接数） |

**分析与切入方式**：
- **核心考点**：并发容器选择——不仅仅是知道 ConcurrentHashMap 安全，还要知道为什么它适合这个场景
- **回答思路**：先肯定（ConcurrentHashMap 线程安全），再说为什么合适（读多写少的连接管理场景，分段锁机制性能好），再指出需要注意的（遍历时是否要加同步？send 操作是否需要额外保护？）
- **查漏补缺**：容易忽略"遍历时安全"的问题——ConcurrentHashMap 的 values() 遍历是弱一致的，对 SseEmitter 做批量 send 时可能需要额外同步
- **面试加分**：能指出"connectionMap 的 value（SseEmitter）不是线程安全的"——同一个 session 的多个 send 调用可能并发，需要在业务层加锁或使用消息队列串行化

---

### Q18：用户刷新页面，SSE 断开，正在跑的 Agent 会怎样？

| 维度 | 内容 |
|------|------|
| **作用** | 处理前端连接断开后 Agent 仍在执行的场景 |
| **原因** | SSE 断开时 SseEmitter 抛出异常，SseServiceImpl 会 remove 连接。但 Agent 的 @Async 线程仍在继续，直到循环结束 |
| **替代** | ① Agent 检测到 SSE 断开后主动终止（onCompletion 回调中标记）② Agent 继续执行（当前行为，消息仍会持久化到 DB，下次打开时能加载） |
| **优化** | ① **断连回滚**：SSE 断开时发中断信号给 Agent 线程（使用 Future.cancel()）② **离线续推**：Agent 继续执行但积压消息，用户重连后一次性推送 ③ **运行超时**：Agent 执行超过一定时间无 SSE 接收端时自动终止 |

**分析与切入方式**：
- **核心考点**：分布式系统中"连接断开"的处理策略——SSE 断开不等于 Agent 应该终止
- **回答思路**：先分析当前行为（Agent 继续执行，消息存 DB），再说好坏（好：消息不丢；坏：浪费计算资源），最后给优化方案
- **查漏补缺**：容易说"Agent 应该终止"——但仔细想想，用户可能只是想刷新页面，Agent 已经在查数据库/调 API，终止了这次执行就白费了。**消息持久化 + 下次加载**是更合理的默认行为
- **面试加分**：能提出"运行可见性"方案——在会话列表中显示"进行中"状态，用户可以等待或手动终止。这比"连接断了就放弃"更符合用户预期

---

### Q19：如何给 SSE 加上心跳机制？

| 维度 | 内容 |
|------|------|
| **作用** | 定期发送 keepalive 消息，防止 SSE 连接因长时间无数据被网关/Nginx 断开 |
| **原因** | 大多数 HTTP 代理（Nginx、Cloudflare）默认 60-120s 无数据就断开连接。Agent 思考/执行阶段可能有较长的静默期 |
| **替代** | ① 周期性发送空注释行（: keepalive\n\n，SSE 协议支持，浏览器不会触发事件）② 缩短 Agent 思考时间（不是技术手段）③ WebSocket（自带 ping/pong） |
| **优化** | ① 心跳间隔可配置（30-60s）② 使用 ScheduledExecutorService 定时发送 ③ 结合 SseEmitter.onTimeout 设置超时时间（默认 30 分钟） |

**分析与切入方式**：
- **核心考点**：SSE 生产级工程化——知道"连接可能被代理断开"这个坑
- **回答思路**：先说为什么需要（Nginx 超时配置），再说怎么实现（定时任务发 keepalive），最后给出最佳实践（心跳间隔 = 代理超时时间的一半）
- **查漏补缺**：容易只说"加心跳"说不出具体实现。关键点：SSE 协议中空注释行 :keepalive\n\n 浏览器会自动忽略
- **面试加分**：能给出心跳的"智能"方案——只在 Agent 执行期间发心跳（空闲时不发），节省带宽。结合 Agent 状态机：IDLE 状态不发，THINKING/EXECUTING 状态定期发

---

## 第六阶段：多模型注册表

```
ChatClientRegistry: Map<ModelType, ChatClient>
初始化: @PostConstruct 从 application.yaml 读取配置，构建各模型 Client
切换: Agent 表的 model 字段 → JChatMindFactory 中 registry.get(agent.getModel())
```

---

### Q20：注册表模式怎么实现的？

| 维度 | 内容 |
|------|------|
| **作用** | 集中管理多个 AI 模型的 ChatClient 实例，实现模型切换的配置化 |
| **原因** | 不同模型有不同的 API 地址、Key、参数，需要在启动时统一初始化，运行时按 Agent 配置切换 |
| **替代** | ① if-else 硬编码（每加一个模型改一次代码）② 工厂模式 + 策略模式（更灵活但代码量更大） |
| **优化** | ① 运行时动态注册（管理端 API 新增模型，不需要重启）② 灰度切换（同一个模型两个版本共存，按 Agent 比例分流）③ 健康检查（定时验证模型 API 可用性，不可用时自动切备用） |

**分析与切入方式**：
- **核心考点**：是否理解"注册表 = Map + 初始化逻辑"这个简单但有效的模式
- **回答思路**：先说实现（@PostConstruct 读取配置 → 构建 ChatClient → put 到 EnumMap<ModelType, ChatClient>），再说使用（Factory 中 registry.get(modelName)），最后说扩展（新模型只需在配置 + 枚举中各加一项）
- **查漏补缺**：容易忘记说"如果模型不存在会怎样"——当前抛 IllegalStateException，但更好的做法是降级到默认模型
- **面试加分**：能对比 Spring Cloud 的 DiscoveryClient 注册表设计——本质都是"名字→实例"的 Map，只是后者多了健康检查。注册表模式是最简单的服务发现

---

### Q21：接入第三个模型要改哪些代码？

| 维度 | 内容 |
|------|------|
| **作用** | 验证多模型系统的可扩展性 |
| **原因** | 注册表模式设计的核心目标就是"新增模型少改代码" |
| **替代** | ① 不改注册表，直接加 if-else（坏实践）② 用配置文件声明全部配置（可读性更好） |
| **优化** | ① 配置热加载（修改 yaml 不用重启）② 模型 API 兼容性测试（新模型接入后自动跑回归测试）③ 模型自动发现（扫描 classpath 下的 ChatClient 实现） |

**分析与切入方式**：
- **核心考点**：可扩展性的验证——不是"设计时说了不算"，真正新增时才知道好不好扩展
- **回答思路**：三步：① ModelType 枚举加一项 ② application.yaml 加配置 ③ ChatClientRegistry 加构建逻辑。强调"不需要改任何业务代码"
- **查漏补缺**：注意 Spring AI 的 ZhiPuAiChatModel 和 DeepSeekChatModel 的构建参数是不同的——注册表需要处理这种差异
- **面试加分**：能说出"更好的做法"——用 @ConditionalOnProperty 或 SPI 机制，新模型自动注册，完全不需要改核心代码。类似 Spring Boot 的自动配置

---

### Q22：Agent 配置了不存在的模型名会怎样？

| 维度 | 内容 |
|------|------|
| **作用** | 处理配置错误的异常场景 |
| **原因** | Agent 的 model 字段来自数据库用户配置，可能填写了不存在的模型名 |
| **替代** | ① 返回错误（当前做法：IllegalStateException）② 降级到默认模型（自动切换）③ 校验时拒绝保存（前端+后端双重校验） |
| **优化** | ① 模型发现接口：前端创建 Agent 时只展示可用模型下拉框（不让用户手填）② 健康检查：定期验证所有注册的模型是否可用③ 自动降级：注册表中找不到时自动走默认模型 + 打日志告警 |

**分析与切入方式**：
- **核心考点**：异常处理 + 用户体验设计——不只要"知道会报错"，还要"知道怎么让用户不犯错"
- **回答思路**：先说当前行为（抛异常，Agent 创建失败），再说更好的做法（前端只展示可用模型、后端自动降级）
- **查漏补缺**：容易只说"抛异常"——只说异常处理不够，要主动提出"预防性设计"
- **面试加分**：结合"防御性编程"和"容错设计"两个理念——前者（校验、下拉框）防止用户犯错，后者（降级、默认模型）在犯错时减少影响

---

## 第七阶段：数据模型与分层设计

```
Entity: 与数据库表一一映射（MyBatis）
DTO: 业务传输对象（转换 JSONB 字段类型）
VO: 前端展示视图对象（脱敏、格式化）
Request/Response: API 契约
```

---

### Q23：为什么分 Entity / DTO / VO 这么多层？

| 维度 | 内容 |
|------|------|
| **作用** | 每层各司其职，避免耦合：Entity 不暴露给前端，VO 不污染数据库 |
| **原因** | ① 安全：Entity 可能包含敏感字段（密码、密钥），VO 可以脱敏 ② 灵活：数据库字段变更不影响前端 API，反之亦然 ③ 类型适配：JSONB 字段在 Entity 是 String，在 DTO 转为 List<String> |
| **替代** | ① 直接用 Entity 返回前端（不安全、不灵活）② 只有 VO 没有 DTO（业务逻辑和展示逻辑混在一起） |
| **优化** | ① 使用 MapStruct 自动转换（减少样板代码）② 统一转换器（Converter 类集中管理 Entity↔DTO↔VO 映射）③ 加 Validation 注解校验输入 |

**分析与切入方式**：
- **核心考点**：分层设计的工程化理解——不只是知道"要分层"，还要知道"每层解决什么问题"
- **回答思路**：先说"分层解决的核心问题"（安全、灵活、类型适配），再拿项目中的具体例子（Agent.allowed_tools 从 String→List<String> 的转换），最后说成本（代码量增加）
- **查漏补缺**：容易只背概念，说不出项目中的具体例子。用 Agent 表的 JSONB 字段举例子最有力
- **面试加分**：能主动指出**过度分层**的问题——对于简单的 CRUD（如字典表），DTO/VO/Entity 三层可能冗余。好的架构是"该分时分，不该分时别硬分"

---

### Q24：JSONB 字段的转换过程是怎样的？

| 维度 | 内容 |
|------|------|
| **作用** | 将数据库的 JSONB 类型（字符串）转换为 Java 的 List/DTO 类型 |
| **原因** | MyBatis 读取 JSONB 返回 String，需要 Jackson/ObjectMapper 反序列化为目标类型 |
| **替代** | ① 直接用 String 在前端解析（不够安全，前端要处理 JSON 解析）② 数据库用普通文本字段（失去 JSONB 的索引和校验能力） |
| **优化** | ① 自定义 TypeHandler（如 PgVectorTypeHandler），MyBatis 自动转换 ② 缓存反序列化结果（同一字段多次读取避免重复解析）③ 加 JSON Schema 校验（写入时校验 JSONB 结构） |

**分析与切入方式**：
- **核心考点**：MyBatis + JSONB 的集成方法——知道 TypeHandler 这个扩展点
- **回答思路**：全链路：数据库 JSONB → MyBatis 读为 String → Converter 用 ObjectMapper 反序列化为 DTO 中的 List → 存入 VO 返回前端。关键组件：Jackson + 自定义 Converter
- **查漏补缺**：容易忽略 TypeHandler（PgVectorTypeHandler）——它是 MyBatis 层面处理 pgvector 类型的关键，没有它 MyBatis 无法把 PostGIS 向量类型映射为 Java 对象
- **面试加分**：能聊 JSONB 的数据库优势——JSONB 支持索引（GIN 索引可以加速 JSON 字段查询）、支持校验（CHECK (metadata IS JSON)）、比纯文本更节省存储（二进制格式）

---

### Q25：PgVectorTypeHandler 的作用？

| 维度 | 内容 |
|------|------|
| **作用** | MyBatis TypeHandler 实现，处理 pgvector 类型与 Java float[] 之间的双向映射 |
| **原因** | pgvector 的 vector 类型是 PostgreSQL 扩展类型，MyBatis 默认不支持，需要自定义 TypeHandler 做序列化/反序列化 |
| **替代** | ① 用 String 存向量（文本形式 "[0.1,0.2,...]"，灵活性差）② 用 JPA + Hibernate 的 pgvector 方言（不需要 TypeHandler，但项目用了 MyBatis） |
| **优化** | ① 检查向量维度匹配（写入时验证维度是否与模型一致）② 缓存序列化结果（同一 embedding 多次写入时避免重复序列化）③ 加向量归一化（写入前自动 L2 归一化） |

**分析与切入方式**：
- **核心考点**：MyBatis 扩展机制 —— TypeHandler 的作用和使用场景
- **回答思路**：先说 TypeHandler 是什么（MyBatis 中处理 Java 类型 <-> JDBC 类型的桥梁），再说项目中的具体实现（float[] <-> pgvector 的 setParameter/getResult），最后说没有它会怎样（MyBatis 报类型转换异常）
- **查漏补缺**：容易只回答"处理 pgvector 类型"但说不出"为什么需要"。强调 MyBatis 内置不支持 PostgreSQL 扩展类型
- **面试加分**：能对比 Spring Data JPA + Hibernate 的 pgvector 方言——JPA 通过方言注册自定义类型，MyBatis 通过 TypeHandler，本质都是告诉 ORM 框架"这个特殊类型怎么读写"

---

## 第八阶段：安全与优化

### 已识别问题清单

| 编号 | 问题 | 等级 | 建议方案 |
|------|------|------|----------|
| S1 | application.yaml 硬编码 API Key | 🔴 高危 | 环境变量 / Vault 密钥管理 |
| S2 | application.yaml 硬编码邮箱密码 | 🔴 高危 | 环境变量 / 加密配置中心 |
| S3 | DataBaseTools SQL 注入 | 🟡 中危 | 只读账号 + JSqlParser 校验 |
| S4 | thinkPrompt 硬编码在 Java 代码 | 🟡 中危 | 配置化 / DB 存储 / 动态生成 |
| S5 | 没有流式输出，全量返回 | 🟡 中危 | 改用 Stream API / WebFlux |
| S6 | SSE 没有心跳，30 分钟断连 | 🟡 中危 | 定时 keepalive 消息 |
| S7 | 前端无 loading 状态 | 🟢 低 | SSE 中 AI_THINKING/AI_EXECUTING 状态渲染 |
| S8 | RAG 只支持 Markdown | 🟢 低 | 加 PDF/Word/HTML 解析器 |
| S9 | MAX_STEPS 硬编码 20 | 🟢 低 | 配置化，Agent 级别可配置 |
| S10 | Ollama 地址硬编码 | 🟢 低 | 配置化 + 断路器 |

---

## 面试备战索引

### 项目介绍（30 秒版）

```
JChatMind 是一个基于 Spring AI + React 的 AI Agent 系统。
它不是简单的"调 API 聊天"，而是实现了完整的 Think-Execute 自主决策循环。
技术上：设计了可扩展的工具框架（FIXED/OPTIONAL）、RAG 知识库检索、
多模型注册表（DeepSeek / 智谱切换）、以及基于 SSE 的实时推送。
我负责 Agent 循环架构设计、RAG 链路实现、以及前后端交互。
```

### 简历写法

**项目名称**: JChatMind — AI Agent 智能助手系统  
**技术栈**: Java 17, Spring Boot 3.5, Spring AI 1.1, React 19, PostgreSQL + pgvector, Ollama  
**关键成果**:
- 实现 ReAct (Think-Execute) 自主决策循环，支持最多 20 轮规划-执行
- 设计 FIXED/OPTIONAL 双模式工具框架，新增工具零核心代码侵入
- 完成 Markdown → Embedding → pgvector 检索的 RAG 全链路
- 采用注册表模式管理多模型，新增模型仅需 3 行配置

### 面试必背 TOP 10

1. Agent Loop 完整流程（Q1 + Q4 组合）
2. 为什么要关 internalToolExecutionEnabled（Q4）
3. RAG 全链路（Q11）
4. SSE 选型理由 + 生产化（Q16 + Q19）
5. 多模型注册表原理（Q20）
6. 事件驱动架构好处（Q2）
7. 项目最大技术难点及解决方案（如工具循环调用 + SQL 注入）
8. 你做的优化改进（重构 thinkPrompt、修复 SQL 排序、加空安全保护）
9. 项目不足之处（无流式输出、API Key 硬编码、单机部署）
10. 再给你一个月做什么（流式输出 + 消息队列 + 监控告警）

---

## 📊 学习进度

| 阶段 | 状态 | 掌握度 |
|------|------|--------|
| 第一阶段：架构全局 | Q1✅ Q2✅ | ⭐⭐⭐⭐ |
| 第二阶段：Agent 核心 | Q3✅ Q4✅ Q5✅ Q6✅ | ⭐⭐⭐⭐ |
| 第三阶段：工具系统 | Q7✅ Q8✅ Q9✅ Q10✅ | ⭐⭐⭐⭐ |
| 第四阶段：RAG 知识库 | Q11✅ Q12✅ Q13✅ Q14✅ Q15✅ | ⭐⭐⭐⭐ |
| 第五阶段：SSE 实时通信 | Q16-19 待回答 | 🔴 |
| 第六阶段：多模型注册表 | Q20-22 待回答 | 🔴 |
| 第七阶段：数据模型 | Q23-25 待回答 | 🔴 |
| 第八阶段：安全与优化 | 已识别 | 🟡 |
