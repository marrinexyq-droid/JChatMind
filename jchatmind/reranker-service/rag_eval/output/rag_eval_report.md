# JChatMind RAG v2 评估报告

> 生成时间: 2026-05-31 14:15:33
> 测试数据: 10 篇量子纠缠领域专业文档
> 评估模式: vector / hybrid / hybrid-rerank

## 检索指标

| 模式 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Precision@1 | Precision@3 | Precision@5 | Precision@10 | MRR | NDCG@5 |
|---|---|---|---|---|---|---|---|---|---|---|
| vector | 0.8421 | 1.0000 | 1.0000 | 1.0000 | 0.8421 | 0.3333 | 0.2000 | 0.1000 | 0.9211 | 0.9417 |
| hybrid | 0.9298 | 1.0000 | 1.0000 | 1.0000 | 0.9298 | 0.3333 | 0.2000 | 0.1000 | 0.9649 | 0.9741 |
| hybrid-rerank | 0.9649 | 1.0000 | 1.0000 | 1.0000 | 0.9649 | 0.3333 | 0.2000 | 0.1000 | 0.9825 | 0.9871 |

## 延迟统计

| 模式 | P50_ms | P95_ms | Mean_ms |
|---|---|---|---|
| vector | 93.7 | 128.0 | 134.2 |
| hybrid | 94.5 | 128.7 | 135.0 |
| hybrid-rerank | 8649.6 | 11286.8 | 8870.4 |

## 结论

### Hybrid vs Vector-only

| Recall@1 | 0.8421 | 0.9298 | +10.4% |
| Recall@3 | 1.0000 | 1.0000 | +0.0% |
| Recall@5 | 1.0000 | 1.0000 | +0.0% |
| Recall@10 | 1.0000 | 1.0000 | +0.0% |


### Rerank vs Hybrid (Precision)

| Precision@1 | 0.9298 | 0.9649 | +3.8% |
| Precision@3 | 0.3333 | 0.3333 | +0.0% |


### 延迟开销

以 P50 总延迟为基准，Hybrid 相比 Vector 增加了 BM25 全文检索，
Hybrid+Rerank 在此基础上增加了 Cross-Encoder 精排。

### 综合建议

基于以上数据，推荐默认模式根据延迟要求选择：
- 低延迟场景: **hybrid** (无 rerank)
- 高质量场景: **hybrid-rerank** (Cross-Encoder 精排)
