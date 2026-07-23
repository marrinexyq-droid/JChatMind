# JChatMind — AI 智能体助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI 智能体助手，基于 Spring AI 构建，实现自主决策、工具调用和 RAG 知识库检索。

## 技术栈

- Spring AI + Java 后端
- PostgreSQL + pgvector（RAG 知识库）
- Python 3.11 + Chroma + MCP（新 RAG 替换链路，受控切流中）
- DeepSeek / 智谱 AI 多模型支持
- SSE 实时通信
- Think-Execute Agent 循环
- React + TypeScript 前端

## 现有 Java RAG v2 架构

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

## Python RAG 收敛链路

Python 子系统正在沿受控 Bridge 替换既有 Java RAG 内核，当前链路为：

```text
Markdown / PDF
  → Loader Factory → 清洗与元数据 Transform → 语义分块
  → Ollama BGE-M3 Embedding
  → Chroma Dense Index + SQLite Sparse Index
  → Hybrid Retrieval / Rerank
  → 基于证据的 AnswerGenerator（[C1]、[C2] 引用约束）
  → MCP stdio → Java Bridge → Agent / SSE / React
```

索引写入采用 fail-closed 一致性门禁：Embedding 配置变化、替换写入失败或 Dense/Sparse
部分删除失败时，查询会返回 `re-index required`，避免混用不兼容向量或暴露残留证据。

## 近期开发时间线

| 日期 | 阶段 | 已完成内容 |
|---|---|---|
| 2026-07-03 | Python RAG 骨架与 MVP | 建立 `rag-mcp` 配置、核心契约、Trace、评估指标、Markdown 摄取、Hybrid Retrieval、严格 RAGAS 数据集、MCP stdio 工具层与受控 Java Query Bridge；同时接入 Google Gemini ChatClient。 |
| 2026-07-04 | Bridge 与可观测性 | 增加 Dashboard、Reranker seam、Java 摄取/删除同步、Bridge readiness 健康检查和 `rag-canary` Profile。 |
| 2026-07-06 | Canary 自动化 | 完成隔离 Smoke、Java 启动前 Preflight、多轮 Acceptance Gate、根目录统一验证脚本和 GitHub Actions 工作流。 |
| 2026-07-08 | 发布门禁与存储收敛 | 增加 Cutover Readiness 报告、Judge-model RAGAS Gate，并将 Chroma 设为 Dense Vector Store 主实现，保留本地 SQLite 降级。 |
| 2026-07-13 | 收敛 Task 1–6 | 清理重复产物并保护工作区缓存；移除已提交 Secret 默认值并增加全仓扫描；锁定 Python 3.11/uv 环境；让 Embedding 配置真正驱动运行时；补齐索引原子性与兼容性门禁；支持文本型 PDF 摄取；生成带有效证据引用的回答。 |
| 2026-07-17 | 收敛 Task 7 | 增加当前 Pipeline Golden-set runner 与独立 JSON 报告，通过 source path/heading 将运行时 chunk 映射到稳定 Golden context；Judge-RAGAS 的 generated policy 只接受该报告；Canary 2.7 以实时 Recall@1/MRR、全量 Judge 和 Runtime Smoke 作发布结论，并严格拒绝无效 Golden schema、空 case、case error、空答案、reference/evidence fallback 和 SQLite VectorStore。 |
| 2026-07-23 | 收敛 Task 8 | 将同一份 Python 查询 Trace 通过 `SearchResponse` 和 MCP structured content 透传 `trace_id`/`trace_stages`，以安全快照呈现 dense、sparse、fusion、rerank 与 response 阶段；Java Bridge 改为映射真实阶段和 fallback 状态，不再把最终引用伪装成完整 RRF Trace；旧版 MCP 响应继续兼容并显式标记 `partial=true`，React 沿用现有 `ragTrace` 消费协议。 |

当前 [RAG 收敛计划](docs/superpowers/plans/2026-07-13-rag-convergence.md) 已完成 Task 1–8
的代码实现，Python 全量测试最新记录为 **168 passed**，Java 非在线示例测试为 **71 passed**，
前端生产构建已通过；现有 ESLint 基线仍有 32 个错误，留待 Task 8A 专项修复。本机严格 current-pipeline 运行已
正确保持 Chroma 且 fail-closed，但因 Ollama `localhost:11434` 未运行而返回 `failed`；
因此 P3 运行时 Gate 尚未宣告通过。下一阶段是前端基线质量门禁和 Canary burn-in；
在这些门禁通过前，默认 Profile 仍保留 Java RAG fallback，
Cutover Readiness 维持 `not_ready`。历史暴露凭证仍必须由仓库所有者在外部平台完成
轮换，代码扫描不能代替凭证撤销。

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

## RAG deep-dive interview notes

This project now treats RAG as the main technical depth line: retrieval is not a
single vector search call, but an observable and measurable pipeline.

### Adaptive RAG pipeline

```text
Markdown upload
  -> heading-aware chunking
  -> BGE-M3 embedding
  -> GraphRAG-lite entity/relation indexing

User query
  -> rule-based query planner
  -> vector search + BM25
  -> RRF fusion
  -> optional GraphRAG-lite 1-2 hop expansion for multi-hop queries
  -> optional cross-encoder rerank
  -> context reorder
  -> Self-RAG evidence gate
  -> cited answer with [C1], [C2] evidence markers
```

### Evaluation snapshot

The current evaluation set under `jchatmind/reranker-service/rag_eval` contains
58 labeled questions over 10 quantum-entanglement documents. The baseline report
shows why the default router keeps `hybrid` fast and reserves rerank for complex
queries:

| Mode | Recall@1 | MRR | NDCG@5 | P50 latency |
|---|---:|---:|---:|---:|
| vector | 0.8421 | 0.9211 | 0.9417 | 93.7 ms |
| hybrid | 0.9298 | 0.9649 | 0.9741 | 94.5 ms |
| hybrid-rerank | 0.9649 | 0.9825 | 0.9871 | 8649.6 ms |

### Engineering tradeoff case

For exact factual questions, `hybrid` is usually the best default: BM25 recovers
hard terms and model names while vector retrieval covers semantic paraphrases.
For comparison or multi-hop questions, the planner switches to `hybrid-rerank`;
multi-hop queries also enable GraphRAG-lite expansion so chunks connected through
shared entities can enter the candidate pool before rerank. If retrieved evidence
is sparse, the Self-RAG gate retries with rerank or a larger pool; if evidence is
still insufficient, the tool returns an explicit insufficient-evidence message
instead of forcing the model to guess.

### Trace surface

Every RAG tool call records query type, planned query, retrieval mode, candidate
pool size, vector/BM25/RRF/rerank ranks, GraphRAG-lite expanded chunks, final
chunks, and Self-RAG decisions. The chat UI exposes this in the RAG evidence
panel, so a demo can show not only the final answer but also why those evidence
chunks were selected.

## Google GenAI / Gemini

JChatMind can register a Google Gemini chat client with the model id
`gemini-2.5-flash`. The API key is read only from environment variables and is
not committed to the repository.

PowerShell:

```powershell
$env:GOOGLE_API_KEY = "<your-google-ai-studio-api-key>"
$env:GOOGLE_GENAI_MODEL = "gemini-2.5-flash"
```

Agent model id:

```text
gemini-2.5-flash
```

Optional tuning variables:

```text
GOOGLE_GENAI_TEMPERATURE=0.7
GOOGLE_GENAI_MAX_OUTPUT_TOKENS=2048
GOOGLE_GENAI_TIMEOUT_MILLIS=30000
```

## RAG Canary Verification

Run the project-level RAG canary gate from the repository root:

```bash
python scripts/verify_rag_canary.py --acceptance-rounds 3
```

The verifier runs `rag-mcp` Python tests, the multi-round canary acceptance
gate, and Java bridge tests. GitHub Actions runs the same command in
`.github/workflows/rag-canary-acceptance.yml`.

Check whether the project is ready to make Python RAG the default canonical path:

```bash
python scripts/rag_cutover_readiness.py --allow-not-ready
```

This readiness report is expected to stay `not_ready` until Java RAG internals
are deprecated or removed and the default Spring profile delegates to Python.
The Python subsystem now includes a Chroma-backed canonical vector store path
with a local SQLite fallback, plus strict `--require-chroma` canary gates for
production runtime verification. It also includes a judge-model RAGAS gate for
faithfulness and answer relevancy. Run
`python rag-mcp/scripts/evaluate_ragas_judged.py --mock-judge --limit 5` from
the repository root for a deterministic wiring check, or configure
`RAGAS_JUDGE_*`/`GOOGLE_API_KEY` for a real model judge.
