# JChatMind RAG v2 评估计划书

> 基于《量子纠缠-RAG-数据库设计---Google-Gemini》实验方案
> 适配 JChatMind 现有 RAG v2 Pipeline
> 测试数据：10 篇量子纠缠领域专业文档（计划文档/gemini-code-*.md）

---

## 目录

1. [评估目标](#1-评估目标)
2. [实验设计概述](#2-实验设计概述)
3. [测试数据与 Ground Truth 构建](#3-测试数据与-ground-truth-构建)
4. [评估指标](#4-评估指标)
5. [技术实现方案](#5-技术实现方案)
6. [项目文件结构](#6-项目文件结构)
7. [预期产出与结论框架](#7-预期产出与结论框架)
8. [执行时间线](#8-执行时间线)
9. [附录各组件访问方式](#9-附录各组件访问方式)

---

## 1. 评估目标

### 1.1 核心目标

定量验证 JChatMind RAG v2 Pipeline（Heading+Body Embedding + 三种检索模式）的检索质量与延迟表现，用具体数据证明设计有效性。

### 1.2 需要回答的问题

| # | 问题 | 验证方式 |
|---|------|---------|
| 1 | Hybrid（向量+BM25+RRF）相比纯 Vector 检索，Recall 提升了多少？ | 对比 Recall@K |
| 2 | Cross-Encoder Rerank 相比纯 Hybrid，Precision 提升了多少？ | 对比 Precision@K |
| 3 | Rerank 带来的延迟开销是否可接受？ | 对比 P50/P95 延迟 |
| 4 | BGE-M3 Embedding（Heading+Body）在不同语义粒度下表现如何？ | 父切片 vs 子切片的 Recall 差异 |
| 5 | 检索结果的排序质量如何？ | NDCG@K |

---

## 2. 实验设计概述

### 2.1 实验变量

| 维度 | 设定 |
|------|------|
| Embedding 策略 | **Heading + Body**（固定，对应计划文档 A 组） |
| 检索模式 (自变量) | `vector-only` / `hybrid` / `hybrid+rerank` |
| Top-K (自变量) | K = 1, 3, 5, 10 |
| 测试数据 | 10 篇量子纠缠文档，按子切片增强解析 = ~30 chunk |
| Ground Truth | 文档内现有 Hypothetical_Questions + LLM 补充生成（智谱 GLM） |

### 2.2 对照矩阵

| 实验编号 | 检索模式 | RRF | Rerank | 期望回答的问题 |
|----------|---------|-----|--------|---------------|
| E1 | vector-only | ❌ | ❌ | 纯语义检索基线 |
| E2 | hybrid | ✅ | ❌ | BM25 补充了对 recall 的贡献 |
| E3 | hybrid+rerank | ✅ | ✅ | Rerank 对 precision 的提升 |

### 2.3 评估范围说明

**本计划只覆盖 A 组（Heading+Body Embedding）**，对应 JChatMind 当前 RAG v2 的默认实现。

计划文档中的 B 组（Heading-Only + Parent-Child）、C 组（Body-Only）、D 组（Dynamic Chunk Size）**不在本次评估范围内**，因为当前代码不支持这些策略，如需验证需另行改代码。

---

## 3. 测试数据与 Ground Truth 构建

### 3.1 测试文档

10 篇量子纠缠文档（`计划文档/gemini-code-*.md`）涵盖 4 个知识层级：

| 层级 | 文档 | 主题 |
|------|------|------|
| Level 1 基础理论 | doc_001, doc_007 | 贝尔态、叠加vs纠缠区别 |
| Level 2 数学推导 | doc_002, doc_004 | 纠缠度测量、CHSH不等式 |
| Level 2 物理哲学 | doc_003 | EPR佯谬 |
| Level 3 实验物理 | doc_005 | 阿斯佩实验 |
| Level 3 工程硬件 | doc_008, doc_009 | 超导比特、离子阱 |
| Level 3 协议应用 | doc_006, doc_010 | 隐形传态、E91协议 |

### 3.2 增强分块策略

**解析器增强规则**：识别文档中以下结构标记作为分块边界：

```
====== 父切片开始 (Parent Chunk) ======   → chunk 开始
# ID: xxx                                 → 元数据
# Title: xxx                              → chunk 标题（存入 content）
# Level: N                                → 元数据
... 父切片正文 ...
------ 子切片嵌套 (Child Chunk) ------   → chunk 开始
# ID: xxx                                 → 元数据
# Tags: [A, B, C]                         → 元数据
# Hypothetical_Questions: [...]           → 元数据
... 子切片正文 ...
------ 子切片嵌套结束 ------               → chunk 结束
... 父切片剩余正文 ...                     → chunk 开始
====== 父切片结束 ======                   → chunk 结束
```

**每篇文档产出 3 个 chunk**：

| chunk 索引 | 内容范围 | 大小特征 |
|-----------|---------|---------|
| chunk_0 | 父切片 Introduction（文档背景介绍） | 中等（~300-500 tokens） |
| chunk_1 | 子切片完整内容（核心知识点） | 小到中等（~200-400 tokens） |
| chunk_2 | 父切片 Conclusion（技术收敛与总结） | 较小（~100-200 tokens） |

### 3.3 Ground Truth 构建（B 方案）

**Ground Truth 格式**：

```json
{
  "query_id": "q001",
  "query": "什么是最大纠缠态？四个贝尔态的数学表达式是什么？",
  "ground_truth_chunk_ids": ["doc_001_chunk_1"],
  "source": "hq",
  "doc_id": "doc_001",
  "level": 1
}
```

**数据来源 1：已有 Hypothetical_Questions（30 条）**

直接从子切片的 `Hypothetical_Questions` 字段提取，每条 HQ 对应的 ground truth 就是该子切片自身所在的 chunk。

**数据来源 2：LLM 补充生成（~30 条）**

对父切片的 Intro 和 Conclusion chunk，调用智谱 GLM 生成反向查询：

```
请根据以下文本内容，生成 2-3 个只能由这段文本才能准确回答的专业问题。
问题需要覆盖文本的核心知识点，不要过于宽泛。

文本：
{chunk.content}

要求：
- 问题应该具体，提到关键概念（如贝尔态、CHSH不等式、退相干时间 T1）
- 每个问题应该能被文本中不超过 3 句话回答
- 输出格式：每行一个问句
```

**总测试集规模**：约 50-60 条 query。

### 3.4 Ground Truth 质量保障

1. **自动校验**：GT 构建后验证每个 `ground_truth_chunk_ids` 确实存在于数据库中
2. **去重**：移除语义重复的 query（cosine similarity > 0.95 的合并）
3. **类别均衡**：确保每个文档、每个层级覆盖均匀

---

## 4. 评估指标

### 4.1 检索端指标（自动计算，不需要 LLM）

| 指标 | 定义 | 公式 | 对应计划文档 |
|------|------|------|------------|
| **Recall@K** | 正确答案在 top-K 中的比例 | #相关chunk在topK中 / #总相关chunk | Context Recall |
| **Precision@K** | top-K 中有多少是相关的 | #相关chunk在topK中 / K | Context Relevance |
| **MRR** | 第一个正确答案的排位倒数 | mean(1 / rank_of_first_relevant) | 补充指标 |
| **NDCG@K** | 排序质量（带 graded relevance） | DCG@K / IDCG@K | 补充指标 |
| **平均 Score** | 检索返回分数的统计分布 | mean / std / min / max | 补充指标 |

**Graded Relevance 定义**：

| 相关程度 | 分值 | 条件 |
|---------|------|------|
| 完全匹配 | 2 | chunk_id 直接命中 ground_truth |
| 同文档相关 | 1 | chunk 与 query 同属一个文档但不是目标 chunk |
| 不相关 | 0 | 以上皆否 |

### 4.2 生成端指标（LLM-as-Judge，智谱 GLM）

| 指标 | 定义 | 打分 Prompt 核心逻辑 |
|------|------|-------------------|
| **Faithfulness（忠实度）** | 生成的回答是否严格基于检索到的上下文 | "请评估以下回答是否完全基于提供的文档内容，没有编造或超出文档范围的信息。打分 0.0-1.0。" |
| **Answer Relevance（回答相关性）** | 回答是否直接回答用户问题 | "请评估以下回答是否直接针对用户问题给出了有价值的回答，没有偏离或回避。打分 0.0-1.0。" |

**评估流程**：

```
query + retrieved_chunks
  → 智谱 GLM 基于 chunk 生成答案
  → 智谱 GLM 对 (query, answer, chunks) 三元组打分
  → 取 3 次打分的均值（减少随机波动）
```

### 4.3 延迟指标

| 指标 | 单位 | 采集方式 |
|------|------|---------|
| Embedding 耗时 (P50/P95) | ms | Python time.time() 包裹 doEmbed 调用 |
| Vector Search 耗时 (P50/P95) | ms | Python 计时 PostgreSQL ORDER BY <-> 查询 |
| BM25 Search 耗时 (P50/P95) | ms | Python 计时 PostgreSQL ts_rank_cd 查询 |
| Rerank 耗时 (P50/P95) | ms | Python 计时 /rerank API 调用 |
| 全链路端到端耗时 (P50/P95) | ms | 各阶段耗时之和 |

### 4.4 指标汇总表格式

```
============================== 检索指标对比 ==============================

模式              Recall@1  Recall@3  Recall@5  Precision@3  MRR     NDCG@5
vector-only       0.XXX     0.XXX     0.XXX      0.XXX        0.XXX   0.XXX
hybrid            0.XXX     0.XXX     0.XXX      0.XXX        0.XXX   0.XXX
hybrid+rerank     0.XXX     0.XXX     0.XXX      0.XXX        0.XXX   0.XXX

                              Hybrid 相比 Vector 提升: +XX.X%
                              Rerank 相比 Hybrid 提升: +XX.X%

============================== 延迟指标 (ms) ==============================

模式               Embed P50  Search P50  BM25 P50  Rerank P50  总 P50  总 P95
vector-only        XX.Xms      XX.Xms       -          -          XX.Xms  XX.Xms
hybrid             XX.Xms      XX.Xms      XX.Xms      -          XX.Xms  XX.Xms
hybrid+rerank      XX.Xms      XX.Xms      XX.Xms     XX.Xms      XX.Xms  XX.Xms

============================== 生成端指标 ==============================

模式               Faithfulness  Answer Relevance
vector-only        X.XXX         X.XXX
hybrid             X.XXX         X.XXX
hybrid+rerank      X.XXX         X.XXX

============================== 按文档层级细分 Recall@5 ==============================

层级               vector-only  hybrid  hybrid+rerank
Level 1 基础理论    X.XXX       X.XXX   X.XXX
Level 2 数学推导    X.XXX       X.XXX   X.XXX
Level 3 实验/工程   X.XXX       X.XXX   X.XXX
Level 3 协议应用    X.XXX       X.XXX   X.XXX
```

---

## 5. 技术实现方案

### 5.1 对 JChatMind 零影响原则

评估脚本采用 **纯 Python 实现，不依赖 JChatMind 后端**，直接调用各底层组件：

```
┌─────────────────────────────────────────────────────┐
│                  Python 评估脚本                       │
│                                                      │
│  01_build_ground_truth.py                            │
│    ├─ 智谱 GLM API → 反向生成 query                   │
│    └─  PostgreSQL → 读取 chunk 元数据                  │
│                                                      │
│  02_run_evaluation.py                                │
│    ├─  Ollama HTTP → doEmbed(query)                  │
│    ├─  PostgreSQL → similaritySearch / bm25Search     │
│    ├─  Python 实现 → RRF 融合                         │
│    └─  Reranker HTTP → /rerank                       │
│                                                      │
│  03_compute_metrics.py                               │
│    └─  纯 Python 计算各项指标                          │
│                                                      │
│  04_report.py                                        │
│    └─  生成最终报告                                   │
└─────────────────────────────────────────────────────┘
         │                │                 │
         ▼                ▼                 ▼
    Ollama:11434    PostgreSQL:5432    Reranker:8001
    (bge-m3)        (pgvector)         (BGE-Reranker)
```

**评估脚本不做的操作**：
- ❌ 不启动 JChatMind 后端
- ❌ 不调用任何 JChatMind REST 接口
- ❌ 不写入/修改数据库数据
- ❌ 不修改数据库 schema 或索引
- ❌ 不影响正在运行的 JChatMind 进程

**评估脚本做的事情**：
- ✅ 读取 `chunk_bge_m3` 表中已有的向量和内容
- ✅ 对 query 调 Ollama 做 embedding
- ✅ 用 PostgreSQL 做向量相似度搜索和 BM25 搜索
- ✅ 在 Python 中实现 RRF 融合逻辑
- ✅ 调 Reranker 服务做精排

### 5.2 技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| LLM for GT 构建 | 智谱 GLM | 用户指定 |
| LLM for 生成评估 | 智谱 GLM | 用户指定 |
| Python HTTP | requests | 简洁稳定 |
| PostgreSQL 驱动 | psycopg2 | 成熟 pg 驱动 |
| 向量计算 | numpy | 余弦相似度等 |
| LLM-as-Judge 调用 | zhipuai SDK 或 REST API | 官方支持 |
| 图表生成 | matplotlib | 简单柱状图 |

### 5.3 关键代码实现

#### 5.3.1 Vector Search

```python
import requests
import psycopg2
import numpy as np

def embed_query(text):
    resp = requests.post("http://localhost:11434/api/embeddings", json={
        "model": "bge-m3",
        "prompt": text
    })
    return np.array(resp.json()["embedding"], dtype=np.float32)

def vector_search(query_vec, limit=20):
    conn = psycopg2.connect("dbname=jchatmind user=postgres password=123456")
    cur = conn.cursor()
    vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"
    sql = """
        SELECT id, content, metadata,
               embedding <-> %s::vector AS distance
        FROM chunk_bge_m3
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (vec_str, vec_str, limit))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows  # [(id, content, metadata, distance), ...]
```

#### 5.3.2 BM25 Search

```python
def bm25_search(query, limit=20):
    conn = psycopg2.connect("...")
    cur = conn.cursor()
    sql = """
        SELECT id, content, metadata,
               ts_rank_cd(content_tsv, websearch_to_tsquery('simple', %s)) AS score
        FROM chunk_bge_m3
        WHERE content_tsv @@ websearch_to_tsquery('simple', %s)
        ORDER BY score DESC
        LIMIT %s
    """
    cur.execute(sql, (query, query, limit))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows
```

#### 5.3.3 RRF 融合

```python
RRF_K = 60

def rrf_fusion(vector_results, bm25_results):
    scores = {}
    chunk_map = {}
    for rank, row in enumerate(vector_results):
        cid = row[0]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        if cid not in chunk_map:
            chunk_map[cid] = row
    for rank, row in enumerate(bm25_results):
        cid = row[0]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        if cid not in chunk_map:
            chunk_map[cid] = row
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [chunk_map[cid] + (scores[cid],) for cid in sorted_ids]
```

#### 5.3.4 Rerank 调用

```python
def rerank(query, candidates, top_k=5):
    docs = [c[1] for c in candidates]
    resp = requests.post("http://127.0.0.1:8001/rerank", json={
        "query": query,
        "documents": docs
    })
    scores = resp.json()
    results = []
    for item in scores:
        idx = item["index"]
        if idx < len(candidates):
            results.append(candidates[idx] + (item["score"],))
    results.sort(key=lambda r: r[-1], reverse=True)
    return results[:top_k]
```

#### 5.3.5 LLM-as-Judge

```python
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="...")

def judge_faithfulness(query, answer, context_chunks):
    prompt = f"""
    你是一个 RAG 评估专家。请评估以下 AI 回答是否严格基于提供的文档内容。

    用户问题：{query}

    检索到的文档内容：
    {chr(10).join(context_chunks)}

    AI 回答：{answer}

    评估标准：
    - 1.0 = 完全基于文档，没有编造任何信息
    - 0.5 = 大部分基于文档，但有小部分推断
    - 0.0 = 包含文档中没有的信息或编造

    请只输出一个浮点数（0.0-1.0），不要输出其他内容。
    """
    resp = client.chat.completions.create(
        model="glm-4",
        messages=[{"role": "user", "content": prompt}],
    )
    return float(resp.choices[0].message.content.strip())
```

### 5.4 Token 消耗估算（智谱 GLM）

| 用途 | 调用次数 | 每次输入 | 总 Tokens (估) |
|------|---------|---------|---------------|
| GT 构建（反向生成） | ~20 次 | ~500 tokens | ~10K |
| 生成回答 | ~180 次 (60 query x 3 mode) | ~2000 tokens | ~360K |
| Judge 打分 | ~180 次 (60 query x 3 mode) | ~2500 tokens | ~450K |
| **合计** | **~380 次** | | **~820K tokens** |

---

## 6. 项目文件结构

```
计划文档/
├── 量子纠缠-RAG-数据库设计---Google-Gemini.md    # 原始实验设计（已有）
├── gemini-code-*.md (10个)                        # 测试文档（已有）
│
└── rag_eval/                                      # 新建：评估系统
    ├── RAG_v2_评估计划书.md                        # 本文件（计划书，需从 .opencode/plans/ 移入）
    │
    ├── requirements.txt                           # Python 依赖
    │   ├── requests
    │   ├── psycopg2-binary
    │   ├── numpy
    │   ├── matplotlib
    │   └── zhipuai
    │
    ├── config.py                                  # 配置文件
    │   # 数据库连接、Ollama 地址、Reranker 地址、
    │   # 智谱 API Key、模型名称
    │
    ├── data/
    │   └── queries.json                           # Ground Truth 数据集
    │
    ├── scripts/
    │   ├── 01_build_ground_truth.py               # Phase 1: GT 构建
    │   ├── 02_run_evaluation.py                   # Phase 2: 检索执行
    │   ├── 03_compute_metrics.py                  # Phase 3: 指标计算
    │   └── 04_report.py                           # Phase 4: 报告生成
    │
    └── output/
        ├── raw_results/                           # 原始检索结果 (JSON)
        ├── metrics/                               # 计算好的指标 (CSV)
        └── rag_eval_report.md                     # 最终报告
```

---

## 7. 预期产出与结论框架

### 7.1 可交付物清单

| 产出 | 格式 | 说明 |
|------|------|------|
| Ground Truth 数据集 | queries.json | 50-60 条(query, chunk_id) |
| 原始检索结果 | raw_results/*.json | 每条 query 在 3 种模式下的完整结果 |
| 指标表格 | metrics/*.csv | Recall/Precision/MRR/NDCG 表格 |
| 延迟统计 | metrics/*.csv | P50/P95 延迟 |
| 生成端评分 | metrics/*.csv | Faithfulness / Answer Relevance |
| 可视化图表 | .png | 对比柱状图 |
| 最终报告 | rag_eval_report.md | 含全部数据和结论 |

### 7.2 结论验证框架

报告结论将参照计划文档第 5 节的预期，进行逐条验证：

```
【假设 1】Hybrid > Vector-only 在 Recall@5 上存在显著提升
  → 预期: BM25 补充了向量检索遗漏的关键词匹配
  → 实际: Recall@5 从 X.XXX 提升到 Y.YYY，提升 Z.Z%

【假设 2】Rerank 在 Precision 上效果明显
  → 预期: Cross-Encoder 精排后 Precision@3 提升 10-15%
  → 实际: Precision@3 从 X.XXX 提升到 Y.YYY，提升 Z.Z%

【假设 3】不同知识层级对检索模式敏感度不同
  → 预期: Level 2（数学推导）依赖 BM25 的关键词匹配，Level 1（概念）依赖语义
  → 实际: 按层级细分表格 → 验证/否定

【假设 4】Rerank 延迟开销
  → 预期: Rerank 增加 100-200ms (P50)
  → 实际: Rerank P50 = XXms

【综合建议】
  基于以上数据，推荐 JChatMind 默认使用模式: [hybrid / hybrid+rerank]
  理由: ...
```

### 7.3 参考：计划文档原实验结论对照

| 计划文档原预期 | 本计划验证点 | 验证状态 |
|--------------|------------|---------|
| Body-Only 性能垫底 | 本次未覆盖（C 组在后续） | 待后续 |
| Heading-Only 检索极佳 | 本次未覆盖（B 组在后续） | 待后续 |
| Heading+Body + Rerank 最高综合分 | **本次核心验证** | **执行中** |

---

## 8. 执行时间线

| 阶段 | 内容 | 预估时长 |
|------|------|---------|
| **Step 0** | 解析器增强：支持按子切片标记分块 | 1-2 小时 |
| **Step 0** | 上传 10 篇文档到知识库，验证入库成功 | 0.5 小时 |
| **Step 1** | build_ground_truth.py — GT 构建 | 1 小时 |
| **Step 2** | run_evaluation.py — 跑 3 种模式检索 | 2 小时（含 LLM 调用） |
| **Step 3** | compute_metrics.py — 计算指标 | 0.5 小时 |
| **Step 4** | report.py — 生成报告 + 图表 | 1 小时 |
| **合计** | | **~6 小时** |

---

## 9. 附录各组件访问方式

| 组件 | 访问地址 | 认证 | 备注 |
|------|---------|------|------|
| Ollama (bge-m3) | POST http://localhost:11434/api/embeddings | 无 | {"model":"bge-m3","prompt":"..."} |
| PostgreSQL | localhost:5432 / 库名 jchatmind | 用户 postgres / 密码 123456 | 只读 chunk_bge_m3 表 |
| Reranker | POST http://127.0.0.1:8001/rerank | 无 | {"query":"...","documents":[...]} |
| 智谱 GLM | 通过 zhipuai SDK | API Key 需提供 | 用于 GT 生成 + LLM-as-Judge |

### 数据库连接信息

```
host: localhost
port: 5432
database: jchatmind
user: postgres
password: 123456
```

### 执行前需要你提供

1. **智谱 GLM API Key** — 用于 LLM 反向生成和 Judge 打分
2. **使用的具体模型名** — 如 `glm-4`、`glm-4v` 等

---

*计划版本：v1.0*
*日期：2026-05-31*
*基于 JChatMind RAG v2（2026-05-28 更新）*
*测试数据：10 篇量子纠缠专业文档*
*评估框架：独立 Python 脚本，零依赖 JChatMind 后端*
