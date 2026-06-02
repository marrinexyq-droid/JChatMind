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
                          → Top-K 结果 → LLM 生成回答
```

**技术亮点：**
- **语义分块**：基于 Markdown AST 的 heading-aware 分块，embedding 包含标题+正文
- **混合检索**：pgvector HNSW 向量检索 + PostgreSQL tsvector BM25 全文检索
- **RRF 融合**：Reciprocal Rank Fusion (k=60) 合并两路检索结果
- **Cross-Encoder Rerank**：BGE-Reranker-v2-m3 二次精排，显著提升命中率
- **HNSW 索引**：pgvector HNSW 索引 (m=16, ef_construction=64) 加速向量检索
- **Agent 工具调用**：Spring AI @Tool 注解，LLM 自主决策是否触发知识库检索

## 更新日志

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
