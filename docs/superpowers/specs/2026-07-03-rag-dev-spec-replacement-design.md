# RAG DEV_SPEC 替换设计

日期：2026-07-03
收敛决策更新：2026-07-13

## 1. 决策

JChatMind 将使用 `C:/Users/Xyq/Downloads/DEV_SPEC.md` 描述的 Python RAG
框架，逐步替换当前 Java/Spring RAG 实现。

目标不是轻量重构 `RagServiceImpl`，而是建立一个 Python 优先的 RAG
子系统，使它最终成为以下能力的唯一事实来源：

- 文档摄取
- 稠密与稀疏检索
- Rerank
- 引用与答案生成
- Trace 与可观测性
- 评估体系
- 本地管理 Dashboard
- MCP 接入

迁移期间，Java/Spring 应用继续负责聊天、Agent、SSE 和 React 产品界面。
Python 达到功能与质量对等后，Java RAG 不再保留为主实现。

替换采用绞杀者模式：

1. 在现有应用旁边建设 `rag-mcp`。
2. 本地验证摄取、查询、MCP、Trace、Dashboard 和评估。
3. 将 Python 结果与现有 Java RAG 基线比较。
4. 通过 Java Bridge 将聊天与工具调用切换到 Python。
5. Canary 稳定后，将 Python 设为默认路径。
6. 废弃、归档或删除 Java RAG 内部实现。

## 2. 当前状态

当前正式产品仍以 Java/Spring Boot、PostgreSQL 和 pgvector 为主。

关键模块：

- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/agent/tools/KnowledgeTools.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/DocumentFacadeServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/GraphRagServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RerankServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RuleBasedQueryPlanner.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RuleBasedSelfRagEvaluator.java`
- `jchatmind/reranker-service/rag_eval`

当前 Java 查询链路：

```text
KnowledgeTools
  -> QueryPlanner
  -> RagServiceImpl
      -> Ollama BGE-M3 Embedding
      -> pgvector 相似度检索
      -> PostgreSQL tsvector 稀疏检索
      -> RRF 融合
      -> 可选 GraphRAG-lite 扩展
      -> 可选 reranker-service
      -> 上下文重排
      -> RagTrace
  -> SelfRagEvaluator
  -> 带引用的工具响应
```

当前 Java 摄取链路：

```text
DocumentController
  -> DocumentFacadeServiceImpl
      -> 保存上传文件
      -> 解析 Markdown 或 Gemini 输出
      -> 按标题切分
      -> RagService.embed
      -> 写入 PostgreSQL ChunkBgeM3
      -> 建立 GraphRAG-lite 实体索引
```

已有优势：

- 已实现 Hybrid Search。
- 已有本地 FastAPI Reranker。
- 已有 Self-RAG 证据门禁及测试。
- 已有 GraphRAG-lite 多跳扩展。
- React 聊天界面可以显示 RAG Trace。
- `rag_eval` 提供了可复用的检索质量基线。
- Python 已具备 Chroma、FTS5 BM25、RRF、Rerank fallback、JSONL Trace、
  MCP tools、Canary 和 Java Bridge 骨架。

与目标的主要差距：

- `RagServiceImpl` 职责过宽。
- 摄取逻辑仍嵌入 `DocumentFacadeServiceImpl`。
- Python provider 配置尚未真正连接到运行时实现。
- Python 只支持 Markdown 摄取，没有 PDF、图片与 Vision seam。
- Python 查询结果目前主要是检索证据拼装，不是完整 LLM 答案生成。
- Dashboard 多数页面仍是只读骨架。
- 评估主要读取历史 observation，没有通过当前 pipeline 重新运行全部 case。
- 默认 Spring profile 仍关闭 Python Bridge。
- Java RAG 尚未废弃。

## 3. 目标目录与边界

Python 子系统位于仓库顶层：

```text
rag-mcp/
  config/
  src/
    core/
    ingestion/
    libs/
    mcp_server/
    observability/
    storage/
    evaluation/
    dashboard/
  data/
  logs/
  tests/
  scripts/
  main.py
  pyproject.toml
  README.md
```

`rag-mcp` 不取代 Java 聊天、Agent、会话、SSE 或 React UI。它只负责 RAG
领域，并通过少量稳定接口与 Java 集成。

## 4. 目标模块

### 4.1 MCP Server

目的：向 Claude、Copilot 和 Java Bridge 提供标准知识工具。

核心工具：

- `query_knowledge_hub(query, top_k?, collection?, mode?)`
- `list_collections()`
- `get_document_summary(doc_id, collection?)`
- `get_system_status()`

要求：

- 使用 JSON-RPC 2.0 over stdio。
- `stdout` 只输出协议消息。
- 日志进入 `stderr` 或本地日志文件。
- 返回结构化内容，并始终提供文本 fallback。
- 在完成基础切流后，再补齐官方 SDK、一致性测试、resources 和图片内容。

### 4.2 Core Query

对外只暴露深模块接口：

```text
QueryEngine.search(request: SearchRequest) -> SearchResponse
```

内部职责：

- QueryProcessor：规范化、关键词提取和 filters。
- DenseRetriever：真实 Embedding + Chroma。
- SparseRetriever：本地 BM25。
- Fusion：RRF 融合。
- Reranker：none、HTTP Cross-Encoder 或 LLM adapter。
- AnswerGenerator：基于证据生成答案。
- ResponseBuilder：组装答案、引用和可选图片。

`QueryEngine` 必须隐藏检索细节，调用方不得直接编排 Dense、Sparse、RRF
和 Rerank。

### 4.3 Ingestion Pipeline

主接口：

```text
IngestionPipeline.run(source_path, collection="default", on_progress=None)
  -> IngestionResult
```

流水线：

```text
FileIntegrity
  -> Loader
  -> Splitter
  -> Transform
  -> Embedding
  -> Upsert
```

第一阶段支持：

- PDF 转规范 Markdown。
- Markdown 直接摄取。
- 基于标题与递归规则的切分。
- 规则清理和 metadata enrichment。
- 可关闭的图片描述接口。
- 稳定 chunk ID 与幂等 upsert。
- 进度回调和阶段 Trace。

图片描述没有凭证时必须降级，不能阻塞纯文本摄取。

### 4.4 Libs 可插拔层

需要的稳定 seam：

- `BaseLLM`：OpenAI-compatible、Azure OpenAI、Ollama。
- `BaseVisionLLM`：OpenAI/Azure Vision 和 disabled fallback。
- `BaseEmbedding`：OpenAI-compatible、Ollama 或本地模型。
- `BaseSplitter`：递归 Markdown-aware splitter。
- `BaseVectorStore`：Chroma。
- `BaseReranker`：none、HTTP Cross-Encoder、LLM。
- `BaseEvaluator`：自定义检索指标和 Ragas。

只有预计存在至少两个实现的变化点才提前增加 seam。禁止为了目录对称创建
没有消费者的空接口。

### 4.5 Storage

最终存储决策：

- Chroma：Dense Vector 与 Chunk payload。
- 本地 BM25/FTS5：稀疏检索。
- SQLite `ingestion_history.db`：文件哈希和摄取状态。
- SQLite `image_index.db`：图片路径映射。
- 本地文件系统：原始文档和提取图片。
- `logs/traces.jsonl`：结构化 Trace。

SQLite VectorStore 只作为开发 fallback。生产或严格 Canary 必须要求 Chroma，
不得静默降级后仍报告为生产就绪。

### 4.6 Observability

Trace 接口：

```text
TraceContext(trace_type)
  -> record_stage(name, method, provider, details, elapsed_ms)
  -> finish()
  -> to_dict()
```

摄取阶段：load、split、transform、embed、upsert。
查询阶段：query_processing、dense_retrieval、sparse_retrieval、fusion、
rerank、answer_generation、response_build。

Python Trace 必须通过 MCP 响应传递 trace ID 或可关联标识。Java Bridge 不应把
Python 结果伪装成完整的 Java Trace。

Dashboard 最终包含：

- Overview
- Data Browser
- Ingestion Manager
- Ingestion Traces
- Query Traces
- Evaluation Panel

### 4.7 Evaluation

基础指标：

- Hit Rate
- Recall@K
- Precision@K
- MRR
- NDCG@K
- 延迟

生成指标：

- Faithfulness
- Answer Relevancy

发布门禁必须运行当前 pipeline。历史 observation、reference-answer fallback 和
mock judge 只能验证评估工具本身，不能作为当前系统质量通过的证据。

最小切流标准：

- Python Hybrid Recall@1 不明显低于 Java Hybrid 基线。
- Python Hybrid-Rerank MRR 不明显低于 Java Hybrid-Rerank 基线。
- 引用包含稳定 chunk ID。
- MCP subprocess E2E 可以完成 `tools/list` 和 `tools/call`。
- 摄取与查询 Trace 可在 JSONL 和 Dashboard 中查看。
- Generated-answer gate 使用当前 pipeline 产生的答案。

## 5. 替换阶段

### 阶段 1：安全与可复现基础

- 删除配置中的可用 secret 默认值。
- 增加 secret scanning。
- 锁定 Python 依赖和版本。
- 提供 Windows 可复现 bootstrap 与验证命令。
- 区分开发 fallback 与严格生产配置。

### 阶段 2：真实摄取与检索闭环

- 增加 PDF Loader。
- 完成 Transform 与 metadata enrichment。
- 将配置连接到真实 Embedding provider。
- 严格 Chroma upsert 与查询。
- 保留 BM25、RRF 和 Rerank fallback。

验收：同一份 PDF 或 Markdown 可以幂等摄取并返回稳定引用。

### 阶段 3：答案生成与真实评估

- 增加 LLM AnswerGenerator。
- 将检索证据、Prompt 和引用规则统一封装。
- 用当前 pipeline 生成 evaluation case 的答案。
- 将真实 retrieval 与 judged metrics 接入 CI。

验收：禁止使用 reference-answer fallback 的严格 gate 可以通过。

### 阶段 4：MCP 与 Java Canary

- 完善 MCP 协议一致性测试。
- 将 Python Trace 标识传递给 Java/React。
- 在 `rag-canary` profile 进行稳定性和回归测试。
- 记录 fallback 次数、延迟和错误率。

验收：Canary 在约定窗口内无质量回退或高频 fallback。

### 阶段 5：默认切流与 Java RAG 退役

- 默认 profile 开启 Python query、ingestion 和 readiness gate。
- 先标记 Java RAG 为 deprecated。
- 稳定后删除 Java 检索、RRF 和 Rerank 编排。
- 保留聊天、Agent、SSE、React 和必要兼容 DTO。

### 阶段 6：管理能力与高级特性

- Dashboard 上传、摄取、删除和评估运行操作。
- Trace 时间线、耗时、Dense/Sparse/Rerank 对比。
- MCP resources。
- 图片提取、caption 与多模态响应。

这些能力不得阻塞阶段 1 至阶段 5 的主闭环。

## 6. 错误处理

摄取：

- 未变化文件返回 skipped。
- Loader 失败记录 failed 状态。
- 单个 Transform 失败尽量按 chunk 降级。
- Embedding 或 Upsert 失败不得标记摄取成功。
- 错误必须写入 Trace，且不能遗留半成功状态。

查询：

- Dense 失败降级到 Sparse。
- Sparse 失败降级到 Dense。
- 两路都失败返回明确 no-evidence。
- Rerank 失败回退到 RRF 排序。
- Answer generation 失败返回带引用的证据文本。

MCP：

- 参数错误返回清晰协议错误。
- 日志不得污染 `stdout`。
- 无证据或下游失败时仍保持响应可解析。

评估：

- 缺少可选依赖时明确失败或 skip。
- Golden set schema 错误必须 fail fast。
- 严格 gate 不得自动降级到 reference answer 或 SQLite VectorStore。

## 7. 测试策略

单元测试：

- Settings 校验与 profile 行为。
- 文件哈希和摄取状态。
- PDF/Markdown Loader contract。
- Splitter 稳定 ID 和 metadata。
- BM25、RRF、Rerank fallback。
- AnswerGenerator 引用约束。
- Trace 序列化。
- MCP 参数和响应格式。

集成测试：

- 摄取写入 Chroma 与 BM25。
- QueryEngine 返回预期 chunk ID。
- MCP subprocess 执行 `tools/list` 和 `tools/call`。
- Dashboard service 读取真实 Trace。
- Java Bridge 保持 React `RagTrace` 兼容。

端到端测试：

- 摄取样例文档。
- 通过 MCP 查询。
- 生成带引用答案。
- 验证 Trace。
- 运行当前 pipeline 的 Golden set 评估。

## 8. Java 资产迁移原则

保留概念：

- Hybrid Search 默认策略。
- RRF。
- 按需 Rerank。
- Self-RAG 证据拒答。
- Trace 可视性。
- 稳定引用标记。

替换实现：

- Java `RagServiceImpl` 内部检索逻辑。
- Java PostgreSQL/pgvector 作为 RAG 主存储。
- `DocumentFacadeServiceImpl` 内嵌摄取逻辑。
- Java 事后拼装 Trace 作为主 Trace。

保留产品能力：

- 聊天、会话、Agent 和 SSE。
- React 产品界面。
- 历史评估数据。
- 可继续复用的 Reranker sidecar。

## 9. 首轮不做的内容

- 完整云端部署。
- 多租户认证授权。
- 完整 GraphRAG 替换。
- CLIP 图片向量检索。
- 重做 React UI。
- 在 Python 对等验证前删除 Java 应用。
- 在主架构稳定前穷尽所有性能调优。

## 10. 实现默认值

- Java 优先通过 MCP stdio 调用 Python。
- 默认真实 Embedding 使用 Ollama BGE-M3。
- OpenAI-compatible Embedding 作为可选 adapter。
- Sparse 使用独立 BM25/FTS5 索引。
- Chroma 是最终 Dense VectorStore。
- 首先复用现有 FastAPI Reranker。
- Markdown 与 PDF 都是一等摄取输入。
- React 保持产品 UI，Streamlit 只作为管理 Dashboard。

## 11. 完成定义

满足以下全部条件后，替换才算完成：

- `rag-mcp` 是唯一 canonical RAG 实现。
- MCP 可以从已索引文档生成带引用答案。
- 摄取增量、幂等且可观测。
- 查询全阶段可追踪。
- Dashboard 可以浏览数据、Trace 并执行管理操作。
- 当前 pipeline 可以在本地和 CI 运行 Golden set 评估。
- Java 聊天与工具调用默认委托给 Python。
- Java RAG 内部实现已废弃、归档或删除。

## 12. 收敛与清理决策

项目从逐版本搭骨架转入单一收敛计划。本文是目标状态的唯一设计来源，
未完成工作只保留一份当前实施计划。已完成历史由 Git 和
`rag-mcp/README.md` 的版本摘要保存，不再永久保留每个小版本的一次性计划。

### 12.1 推进顺序

严格按以下顺序执行，上一阶段验证通过后才能进入下一阶段：

1. 配置与密钥安全。
2. 可复现环境、真实 Embedding 和严格 Chroma。
3. PDF/Markdown 到 LLM 答案与稳定引用的真实闭环。
4. 当前 pipeline + generated answers 的真实评估。
5. Canary、默认切流和 Java RAG 退役。
6. Dashboard 写操作、真实 Trace、MCP resources 和多模态。

### 12.2 仓库清理规则

- 删除不属于当前验证运行的 build、cache、log 和临时目录。
- 删除字节完全一致、保留了 canonical 副本且无代码引用的 tracked 文件。
- 删除无引用旧副本前，确认 Git 或正式来源仍保存其信息。
- 被数据构建、测试、迁移门禁或运行时代码引用的文件必须保留。
- Python 成为验证过的默认路径之前，保留 Java RAG、评估源数据和 Canary 证据。
- `AGENTS.md` 与 `CLAUDE.md` 即使内容相同也保留，因为不同 Agent 运行时发现的
  文件名不同。
- 依赖锁定和 bootstrap 验证之前保留本地 Python 环境；通过门禁后再重建清理。
- 不删除用途未确认的用户未跟踪文件。

当前实施计划必须列出每一个要删除的 tracked 文件，以及证明删除安全的引用
审计或哈希证据。
