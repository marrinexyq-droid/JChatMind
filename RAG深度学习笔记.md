# RAG 深度学习笔记（面试备战版）

> 基于 JChatMind 项目实战 + 大厂真实面经整理
> 日期：2026-05-26

---

## 目录

1. [你的项目 RAG 全链路拆解](#一你的项目-rag-全链路拆解)
2. [项目 RAG 的 5 个缺陷与修复](#二项目-rag-的-5-个缺陷与修复)
3. [RAG 面试基础知识](#三rag-面试基础知识)
4. [大厂真实面经（8 道）](./RAG深度学习笔记.md#四大厂真实面经8-道)
5. [进阶拔高概念](#五进阶拔高概念)
6. [面试评分总结](#六面试评分总结)

---

## 一、你的项目 RAG 全链路拆解

### 整体架构

```
写入端（文档上传 → 可检索）:
  文档上传
    → DocumentFacadeServiceImpl.uploadDocument()
    → MarkdownParserServiceImpl.parseMarkdown()   [flexmark 解析]
    → 按 Markdown 标题分块 (extractSections)
    → ragService.embed(title)                    [bge-m3 1024维]
    → INSERT INTO chunk_bge_m3 (content, embedding)
    → ivfflat 索引

读取端（用户提问 → LLM 回答）:
  User: "问题"
    → JChatMind.think()  → LLM 决定调用 KnowledgeTool
    → execute() → ragService.similaritySearch(kbId, query)
    → doEmbed(query) → float[1024]
    → SQL: ORDER BY embedding <-> query_vec LIMIT 3
    → Top-3 文本片段 → 下一轮 think() → LLM 参考回答
```

### 关键代码位置

| 模块 | 文件 | 行号 |
|------|------|------|
| MD 解析分块 | `MarkdownParserServiceImpl.java` | - |
| Embedding + 检索 | `RagServiceImpl.java` | doEmbed() / similaritySearch() |
| 向量存储 | `ChunkBgeM3Mapper.xml` | similaritySearch SQL |
| Agent 调知识库 | `KnowledgeTools.java` | knowledgeQuery() |
| 上传驱动 RAG | `DocumentFacadeServiceImpl.java` | processMarkdownDocument() |

### Agent 与 KnowledgeTool 交互流程

```
think() → LLM 收到 thinkPrompt（含工具描述 + 知识库列表）
        → LLM 推理"我需要查知识库"
        → 返回 tool_call: KnowledgeTool(kbId, query)

execute() → 执行 ragService.similaritySearch(kbId, query)
          → PostgreSQL: L2 距离排序 LIMIT 3
          → 返回 Top-3 文本片段

下一轮 think() → prompt 包含了检索结果
              → LLM 参考结果回答用户
```

**注意**：LLM 不是靠代码判断"是否缺少上下文"，而是 **thinkPrompt 里的工具描述让 LLM 自主决定是否调用**——这是 ReAct 模式，LLM 自己推理需要外部知识。

---

## 二、项目 RAG 的 5 个缺陷与修复

| # | 缺陷 | 当前做法 | 修复方案 |
|---|------|---------|---------|
| 1 | **只对标题做 embedding** | `embed(title)`，内容不参与检索 | `embed(title + "\n" + content)` |
| 2 | **无重叠窗口（overlap）** | 按标题边界硬切，相邻 chunk 上下文断裂 | 相邻 chunk 重叠 10%-20% 内容 |
| 3 | **单层标题** | 只处理顶层 Heading，嵌套结构丢失 | 递归遍历所有层级 heading，层级拼入标题前缀（如 `1.2.3 标题`） |
| 4 | **大段内容超限** | 一个标题下所有内容合为一个 chunk | 设 MaxChunkSize（512 tokens），超出再切 |
| 5 | **无 Rerank** | Top-3 直接给 LLM | 检索后加 cross-encoder 精排 → 取 Top-2 |

---

## 三、RAG 面试基础知识

### 3.1 pgvector vs 专用向量数据库

| | pgvector | Milvus | Pinecone | Elasticsearch |
|---|---|---|---|---|
| 类型 | PG 插件 | 专用向量数据库 | 云服务 | 搜索引擎 + 向量 |
| 规模 | ~百万级 | 十亿级 | 十亿级 | 千万级 |
| 部署 | 随 PG，零额外运维 | 独立部署（复杂） | 开箱即用（付费） | 独立部署 |
| 索引 | ivfflat / HNSW | IVF / HNSW / DiskANN | 自动 | HNSW |
| 优势 | **一套数据库 + 事务一致** | 性能最强 | 零运维 | 全文搜索最强 |
| 劣势 | 大规模不够 | 运维重 | 贵、数据不在本地 | 向量不是主业 |

**选型公式**：
- 数据 < 100万 + 不想多维护 → **pgvector**
- 数据千万级 + 高性能向量搜索 → **Milvus**
- 不想管运维、有钱 → **Pinecone**
- 需要全文+向量混合评分 → **ES**

**你的项目选 pgvector 的核心理由**：够（规模达不到瓶颈）+ 省（少维护一个中间件）+ 一致（向量和业务数据同一事务）

### 3.2 bge-m3 vs OpenAI text-embedding-ada-002

| | bge-m3 | text-embedding-ada-002 |
|---|---|---|
| 维度 | 1024 | 1536 |
| 部署 | Ollama 本地（免费、数据不出网） | API（按 token 付费） |
| 多语言 | ✅ 中英文都好 | ✅ 但中文不如 bge |
| 延迟 | 本地几毫秒 | 网络几十毫秒+ |
| 隐私 | ✅ 数据不出内网 | ❌ 发到 OpenAI |

**M3 含义**：Multi-Linguality + Multi-Granularity + Multi-Functionality
- Dense（稠密）：你项目用的，整个文本→一个向量
- Sparse（稀疏）：关键词权重，类似 BM25
- Multi-Vector：每个 token 一个向量

### 3.3 RAG vs Fine-tuning

| 维度 | RAG | Fine-tuning |
|------|-----|-------------|
| 知识更新 | ✅ 更新知识库即生效 | ❌ 重训 + 重新部署 |
| 成本 | 低（存向量） | 高（GPU 训练） |
| 可控性 | ✅ 知道引用了哪段文档 | ❌ 黑盒 |
| 幻觉 | ✅ 大幅降低 | 仍然有 |
| 风格/行为驯化 | ❌ 做不到 | ✅ 可以 |
| 推理速度 | 慢（检索+生成两步） | 快（一步生成） |

**核心一句话**：RAG 更新知识，Fine-tuning 驯化行为。

### 3.4 Chunk 策略

| Chunk 大小 | 优点 | 缺点 |
|---|---|---|
| 太小（128t） | 精确定位 | 缺上下文 |
| 适中（256-512t） | 最佳实践 | - |
| 太大（1024t+） | 上下文完整 | 噪声多 |

**硬约束**：不能超过 embedding 模型的最大输入长度（bge-m3 = 8192 tokens）

**规律**：无 Rerank → chunk 宜小；有 Rerank → chunk 可大

### 3.5 BM25 vs 向量检索 vs 混合检索

| | BM25（稀疏） | 向量检索（稠密） |
|---|---|---|
| 优点 | 精确关键词匹配、可解释 | 语义理解、跨语言 |
| 缺点 | 同义词漏检 | 专有名词不可靠 |
| 适合 | 代码/型号/ID | 意图理解/长文本 |

**混合方式**：
1. **RRF 融合**：`score = 1/(k + rank_bm25) + 1/(k + rank_vector)`
2. **先召回再精排**：BM25 Top-20 + 向量 Top-20 → 去重 → Cross-encoder Rerank → Top-3

### 3.6 RAG 优化准确率的 6 个维度

| 维度 | 具体做法 |
|------|---------|
| ① 索引优化 | 优化 chunk 策略 + 重叠窗口 + metadata 过滤 + 多粒度索引 |
| ② 查询优化 | LLM 改写 query + HyDE（假设答案检索）+ Multi-Query |
| ③ 混合检索 | BM25 + 向量 + RRF 融合 |
| ④ 多轮检索 | 判断召回材料是否充分，不够追加检索（Recursive Retrieval） |
| ⑤ **Rerank** | Cross-encoder 对 Top-20 精排 → 取 Top-3（召回率提升 10-15%） |
| ⑥ **评估闭环** | Prompt 约束 + Self-RAG 自检 + RAGAS 量化 + 用户负反馈 |

---

## 四、大厂真实面经（8 道）

### Q1：（美团）RAG 优化准确率，从哪些方向入手？

**参考答案**：见上方 3.6 的 6 个维度。核心：Rerank 是性价比最高的单点优化。

### Q2：（阿里飞猪）用户 query 很短怎么办？

**方案**：
1. **历史上下文补全**——用多轮对话信息扩充 query
2. **Query 扩展**——HyDE（让 LLM 先生成假设答案再检索）+ 同义词扩展 + Multi-Query（生成 3-5 个角度分别检索后去重）
3. **主动澄清**——LLM 明确说"请补充"而非瞎猜
4. **Multi-Query Retrieval**：LLM 把"价格"扩展成 3-5 条查询（"产品定价"、"收费标准"、"套餐价格"），分别检索后去重合并

### Q3：（腾讯 QQ）多条匹配，只能给 LLM 有限上下文，怎么取舍？

**方案**：
1. **混合检索 → Rerank 排序** → BM25 Top-10 + 向量 Top-10 → RRF → Cross-encoder 精排
2. **相关性阈值过滤** → 低于设定分数直接丢弃
3. **Token 预算动态分配** → 计算可用 tokens，按排序依次装入 chunk
4. **Contextual Compression** → 对每个 chunk 做 LLM 压缩摘要，优先送摘要

### Q4：RAG vs Fine-tuning 怎么选？

核心：RAG 更新知识，Fine-tuning 驯化行为。
- 高频变化、准确优先 → RAG
- 风格/语气/个性化 → Fine-tuning
- 最佳实践：两者结合

### Q5：选 pgvector 还是 Milvus？

数据 < 100万 + 不想多维护 → pgvector；千万级 + 性能敏感 → Milvus

### Q6：选 bge-m3 还是 OpenAI embedding？

隐私/成本/中文 → bge-m3；英文/预算充足/不想本地部署 → OpenAI

### Q7：Chunk 大小怎么选？

256-512 tokens 是常见最佳实践，上限不超过 embedding 模型窗口。无 Rerank 宜小，有 Rerank 可大。

### Q8：RAG 检不到知识时模型强行编答案，怎么监控和兜底？

**三层防守**：
1. **前控制**（Prompt）——引用约束提示：只基于上下文作答，不知就说不知
2. **中自检**（Self-RAG）——LLM 生成后自问"有文档支持吗？"，低置信→重新检索
3. **后反馈**（用户负反馈）——点踩记录→分析是召回还是生成问题→针对性补文档/改 prompt

---

## 五、进阶拔高概念

### 5.1 Graph-RAG（微软提出）

**概念**：不是纯向量检索，而是从文档中抽取出实体和关系，构建知识图谱。查询时走图路径推理而非单纯语义相似。

**举个例子**：
- 传统 RAG：搜"苹果"→ 找到含"苹果"的 chunk
- Graph-RAG：搜"苹果"→ 图上关联到库克、iPhone、iOS、App Store → 多跳推理后回答

**效果**：对多跳推理、关系型问题的准确率大幅提升。

**缺点**：构建成本高，需要 NLP 抽取实体关系。

### 5.2 Self-RAG

**概念**：LLM 在生成答案的同时输出一个「置信标记」（support/not support），低置信时触发重新检索或给出不确定性提示。

**你项目中的应用**：可以在 thinkPrompt 里加一句"如果你认为检索到的内容不足以回答问题，请说明并询问用户是否可以提供更多信息。"

### 5.3 Agentic RAG

**概念**：RAG 不再是一次检索就结束的线性流程，而是 Agent 在循环中自主决策何时检索、检索什么、是否要多次检索。

**你的项目已经属于 Agentic RAG**——KnowledgeTool 是 Agent 在循环中自主决定是否调用。这是生产级 RAG 和 Demo 级 RAG 的分水岭。

### 5.4 评估体系（RAGAS）

| 指标 | 意义 |
|------|------|
| Faithfulness | 答案是否忠于检索到的上下文 |
| Answer Relevancy | 答案是否回答了问题 |
| Context Precision | 检索到的内容是否都相关 |
| Context Recall | 相关的内容是否都检索到了 |

**定位问题**：
- Faithfulness 低 → 生成端问题（改 Prompt）
- Context Recall 低 → 检索端问题（改 chunk / embedding / 检索策略）

---

## 六、面试评分总结

| 题目 | 你的评分 | 不足 |
|------|---------|------|
| RAG 全链路 | ⭐⭐⭐⭐⭐ | 完整 |
| pgvector 选型 | ⭐⭐⭐⭐⭐ | 需要补齐对比知识 |
| chunk 策略缺陷 | ⭐⭐⭐⭐ | 漏了"只 embed 标题"和 rerank |
| RAG vs Fine-tuning | ⭐⭐⭐⭐⭐ | 理解到位 |
| BM25 vs 向量 vs 混合 | ⭐⭐⭐⭐⭐ | 推理正确 |
| 优化准确率 6 维度 | ⭐⭐⭐⭐ | 漏了 Rerank 和 Prompt 约束 |
| 短 query 处理 | ⭐⭐⭐⭐⭐ | 三条路径全中 + Multi-Query |
| Top-K 取舍策略 | ⭐⭐⭐⭐ | 说了核心流程，但漏了阈值/预算/压缩 |
| 兜底防幻觉 | ⭐⭐⭐⭐⭐ | 三层防守全中 |

**总体评价**：今天 3 小时，从"知道怎么用"到"能讲清楚为什么"，RAG 面试高频 90% 已覆盖。差的是 Rerank 的原理细节和评估体系的量化指标——这两块临时补一下文档的事。
