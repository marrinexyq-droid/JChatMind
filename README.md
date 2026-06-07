# JChatMind — AI 智能体助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI 智能体助手，基于 Spring AI 构建，实现自主决策、工具调用和 RAG 知识库检索。

## 技术栈

- Spring AI + Java 后端
- PostgreSQL + pgvector（RAG 知识库）
- DeepSeek / 智谱 AI 多模型支持
- SSE 实时通信
- Think-Execute Agent 循环
- React + TypeScript 前端

## RAG v2 架构

JChatMind 实现了完整的 **Hybrid RAG Pipeline**：

```
文档上传 → Markdown AST 语义分块 → BGE-M3 Embedding (heading+body)
                                        ↓
用户查询 → Query Embedding → HNSW 向量检索 (pgvector)
                          → BM25 全文检索 (PostgreSQL tsvector)
                          → Reciprocal Rank Fusion (RRF) 融合
                          → Cross-Encoder Rerank (BGE-Reranker-v2-m3)
                          → Self-RAG 证据质量门控
                          → Top-K 结果 → LLM 生成回答
```

**技术亮点：**
- **语义分块**：基于 Markdown AST 的 heading-aware 分块，embedding 包含标题+正文
- **混合检索**：pgvector HNSW 向量检索 + PostgreSQL tsvector BM25 全文检索
- **RRF 融合**：Reciprocal Rank Fusion (k=60) 合并两路检索结果
- **Cross-Encoder Rerank**：BGE-Reranker-v2-m3 二次精排，显著提升命中率
- **轻量 Self-RAG**：生成前评估证据充分性，必要时自动切换 Rerank 或扩大候选池重检索
- **HNSW 索引**：pgvector HNSW 索引 (m=16, ef_construction=64) 加速向量检索
- **Agent 工具调用**：Spring AI @Tool 注解，LLM 自主决策是否触发知识库检索

## 更新日志

### 2026-06-07 — 轻量前置 Self-RAG

**后端变更：**
- 新增 `SelfRagEvaluator` / `RuleBasedSelfRagEvaluator`，在检索后、生成前判断证据是否足够支撑回答。
- 新增 `SelfRagDecision`、`SelfRagEvaluation`，支持 `ACCEPT`、`RETRY_WITH_RERANK`、`RETRY_WITH_LARGER_POOL`、`INSUFFICIENT_EVIDENCE` 四类决策。
- `KnowledgeTools` 接入 Self-RAG 质量门控：最多补救检索一次，失败时返回证据不足提示，不改变 `[C1]` 引用协议。
- `RagTrace` 新增 Self-RAG 决策、原因和重试次数字段，便于排查“召回不足”和“证据不足”问题。
- `application.yaml` 新增 `rag.self-rag.*` 配置，默认开启轻量规则版 Self-RAG。
- 新增 `RuleBasedSelfRagEvaluatorTest`，并补充 `KnowledgeToolsTest` 覆盖接受、补救和失败降级路径。

**前端变更：**
- `AgentChatHistory` 的 RAG Trace 面板展示 Self-RAG 决策、原因和 retry 次数。
- `types/index.ts` 扩展 `RagTrace` 类型，兼容旧消息 metadata。

### 2026-06-06 — RAG Trace、查询规划与前端体验迭代

**后端变更：**
- `JChatMind` — 明确 Spring AI 使用边界：模型侧使用 `ChatClient.stream()` 获取流式 `ChatResponse`，前端展示仍通过项目自定义 SSE 推送。
- `KnowledgeTools` — 知识库工具返回带 `[C1]`、`[C2]` 标记的证据片段，便于最终回答引用来源。
- `RagService` / `RagServiceImpl` — 新增带 Trace 的混合检索结果，记录向量检索、BM25、RRF、Rerank 等阶段信息，方便定位召回错、排序错和生成错。
- 新增 `QueryPlanner` / `RuleBasedQueryPlanner` — 对用户查询做轻量规划，支持多轮追问时补充上下文。
- 新增 `RagTraceContext`、`RagTrace`、`RagTraceChunk`、`RagSearchResult`、`QueryPlan`、`QueryType` 等模型，用于检索链路追踪和前端展示。
- 新增 `KnowledgeToolsTest`、`RuleBasedQueryPlannerTest`，补充知识库工具和查询规划的单元测试。

**前端变更：**
- `AgentChatView` — 调整 SSE 消息接收和本地消息 upsert 逻辑，避免发送后刷新页面才能看到 AI 回答。
- 新增 `UniversePipelineContext` — 统一接入用户消息、SSE 事件和错误事件，为前端动效与状态联动提供事件管线。
- `AgentChatHistory` — 支持展示 RAG Trace / 来源引用等扩展元数据。
- `PlanetariumScene`、`PlanetariumView`、`data.ts` — 重构行星仪数据和视觉交互，增强聊天过程中的状态反馈。
- `types/index.ts` — 扩展 SSE、RAG Trace 和前端事件相关类型。

### 2026-05-29 — 对话流式输出

**后端变更：**
- `SseMessage` — 新增 `AI_STREAMING_CHUNK` 消息类型，支持流式内容块推送
- `JChatMind` — `think()` 方法重构：`ChatClient.call()` → `.stream()`，LLM 响应实时流式输出
  - 预建空消息记录，获取 `chatMessageId` 后逐 token 追加持久化（`appendChatMessage`）
  - 通过 `Flux<ChatResponse>.doOnNext()` 逐 chunk 推送 SSE
  - 流完成后更新消息 metadata（工具调用信息）
  - 新增 `streamChunk()` 辅助方法统一 SSE 推送逻辑

**前端变更：**
- `types/index.ts` — `SseMessageType` 新增 `AI_STREAMING_CHUNK` 联合类型
- `AgentChatView` — SSE 事件处理新增 `AI_STREAMING_CHUNK` 分支：首个 chunk 创建消息条目，后续 chunk 增量追加内容
- `AgentChatHistory` — 自动滚动逻辑优化：流式内容变化时也触发滚动（不限于新消息）

### 2026-05-28 — RAG v2: 混合检索 + Rerank

**后端变更：**
- `DocumentFacadeServiceImpl` — embedding 输入从仅标题改为标题+正文拼接
- `RagServiceImpl` — 重写为完整 Hybrid Pipeline（向量 + BM25 + RRF + Rerank）
- `RagService` — 新增 `hybridSearch()` 和 `ensureIndexes()` 接口
- `ChunkBgeM3Mapper` — 新增 `bm25Search()`、`ensureTsvColumn()`、`ensureTsvIndex()`、`ensureHnswIndex()`
- `KnowledgeTools` — 改用混合检索，返回格式化结果（含来源+相关度分数）
- `JChatMind` — `MAX_TOOL_RESPONSE_LENGTH` 从 300 提升至 2000
- 新增 `ScoredChunk` VO — 带分数的检索结果数据类
- 新增 `RerankService` / `RerankServiceImpl` — Cross-Encoder Reranking（Ollama bge-reranker-v2-m3）
- 新增 `RagIndexInitializer` — 应用启动时自动初始化 HNSW + GIN 索引

**前端变更：**
- `AddAgentModal` — 填充"检索设置"区域：Top-K 滑块（1-20）、检索模式选择（纯向量/混合/混合+Rerank）
- `api.ts` — 新增 `RagConfig` / `RagMode` 类型

**数据库变更（自动执行）：**
- `chunk_bge_m3` 表新增 `content_tsv` 列（Generated tsvector）
- 新增 GIN 索引 `idx_chunk_content_tsv`（BM25 全文检索）
- 新增 HNSW 索引 `idx_chunk_embedding_hnsw`（向量检索加速）

## 贡献

参考 [CONTRIBUTING.md](CONTRIBUTING.md)

## License

[MIT](LICENSE)
