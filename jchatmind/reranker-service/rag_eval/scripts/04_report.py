"""
Phase 4: 报告生成
- 读取 metrics CSV
- 生成 rag_eval_report.md
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *


def read_csv(filename: str) -> list[list[str]]:
    path = os.path.join(METRICS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.reader(f))


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main():
    retrieval = read_csv("retrieval.csv")
    latency = read_csv("latency.csv")

    # 解析行
    headers = retrieval[0]
    vec = {headers[i]: retrieval[1][i] for i in range(len(headers))}
    hyb = {headers[i]: retrieval[2][i] for i in range(len(headers))}
    rnk = {headers[i]: retrieval[3][i] for i in range(len(headers))}

    # 计算提升
    recall_lines = ""
    for k in TOP_K_LIST:
        v = float(vec.get(f"Recall@{k}", 0))
        h = float(hyb.get(f"Recall@{k}", 0))
        gain = ((h - v) / v * 100) if v > 0 else 0
        recall_lines += f"| Recall@{k} | {v:.4f} | {h:.4f} | +{gain:.1f}% |\n"

    prec_lines = ""
    for k in [1, 3]:
        h = float(hyb.get(f"Precision@{k}", 0))
        r = float(rnk.get(f"Precision@{k}", 0))
        gain = ((r - h) / h * 100) if h > 0 else 0
        prec_lines += f"| Precision@{k} | {h:.4f} | {r:.4f} | +{gain:.1f}% |\n"

    report = f"""# JChatMind RAG v2 评估报告

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 测试数据: 10 篇量子纠缠领域专业文档
> 评估模式: vector / hybrid / hybrid-rerank

## 检索指标

{format_table(retrieval[0], retrieval[1:])}

## 延迟统计

{format_table(latency[0], latency[1:])}

## 结论

### Hybrid vs Vector-only

{recall_lines}

### Rerank vs Hybrid (Precision)

{prec_lines}

### 延迟开销

以 P50 总延迟为基准，Hybrid 相比 Vector 增加了 BM25 全文检索，
Hybrid+Rerank 在此基础上增加了 Cross-Encoder 精排。

### 综合建议

基于以上数据，推荐默认模式根据延迟要求选择：
- 低延迟场景: **hybrid** (无 rerank)
- 高质量场景: **hybrid-rerank** (Cross-Encoder 精排)
"""

    out_path = os.path.join(OUTPUT_DIR, "rag_eval_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告 → {out_path}")
    print(report)


if __name__ == "__main__":
    main()
