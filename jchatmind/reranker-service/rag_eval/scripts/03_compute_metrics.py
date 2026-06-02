"""
Phase 3: 指标计算
- 加载 raw_results.json + queries.json
- 计算 Recall@K, Precision@K, MRR, NDCG@K
- 计算延迟统计 P50/P95
- 输出 CSV 到 output/metrics/
"""
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *


def load_data():
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries_data = json.load(f)
    results_path = os.path.join(RAW_DIR, "results.json")
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    return queries_data, results


def chunk_logical_ids(chunk_map: dict, db_ids: list[str]) -> list[str]:
    uuid_to_logical = {}
    for doc_entries in chunk_map.values():
        for entry in doc_entries:
            uuid_to_logical[entry["uuid"]] = entry["logical_id"]
    return [uuid_to_logical.get(dbid, dbid) for dbid in db_ids]


def recall_at_k(gt: list[str], retrieved: list[str], k: int) -> float:
    if not gt:
        return 0.0
    hits = sum(1 for g in gt if g in set(retrieved[:k]))
    return hits / len(gt)


def precision_at_k(gt: list[str], retrieved: list[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    hits = sum(1 for r in top_k if r in gt)
    return hits / k


def mrr(gt: list[str], retrieved: list[str]) -> float:
    for i, rid in enumerate(retrieved):
        if rid in gt:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(gt: list[str], retrieved: list[str], k: int) -> float:
    dcg = 0.0
    for i, rid in enumerate(retrieved[:k]):
        rel = 1.0 if rid in gt else 0.0
        dcg += rel / math.log2(i + 2)
    n = min(len(gt), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(n))
    return dcg / idcg if idcg > 0 else 0.0


def compute(queries_data: dict, results: list) -> dict:
    chunk_map = queries_data["chunk_map"]
    all_metrics = {}

    for mode in EVAL_MODES:
        buckets: dict[str, list] = {
            **{f"Recall@{k}": [] for k in TOP_K_LIST},
            **{f"Precision@{k}": [] for k in TOP_K_LIST},
            "MRR": [],
            "NDCG@5": [],
        }
        for r in results:
            if "error" in r:
                continue
            gt = r["ground_truth"]
            retrieved = chunk_logical_ids(
                chunk_map,
                [item["id"] for item in r["results"].get(mode, [])],
            )
            for k in TOP_K_LIST:
                buckets[f"Recall@{k}"].append(recall_at_k(gt, retrieved, k))
                buckets[f"Precision@{k}"].append(precision_at_k(gt, retrieved, k))
            buckets["MRR"].append(mrr(gt, retrieved))
            buckets["NDCG@5"].append(ndcg_at_k(gt, retrieved, 5))

        all_metrics[mode] = {
            k: sum(v) / len(v) if v else 0.0 for k, v in buckets.items()
        }
    return all_metrics


def compute_latency(results: list) -> dict:
    all_lat = {}
    for mode in EVAL_MODES:
        totals = [r["timings"].get(mode, {}).get("total_ms", 0)
                  for r in results if "error" not in r]
        totals = [t for t in totals if t > 0]
        if not totals:
            all_lat[mode] = {"P50": 0, "P95": 0, "mean": 0}
            continue
        s = sorted(totals)
        n = len(s)
        all_lat[mode] = {
            "P50": s[int(n * 0.50)],
            "P95": s[min(int(n * 0.95), n - 1)],
            "mean": sum(totals) / n,
        }
    return all_lat


def save_csv(metrics: dict, latency: dict):
    # retrieval
    headers = ["模式"] + [f"Recall@{k}" for k in TOP_K_LIST] \
              + [f"Precision@{k}" for k in TOP_K_LIST] + ["MRR", "NDCG@5"]
    rows = [headers]
    for mode in EVAL_MODES:
        m = metrics[mode]
        rows.append([mode] + [f"{m[f'Recall@{k}']:.4f}" for k in TOP_K_LIST]
                    + [f"{m[f'Precision@{k}']:.4f}" for k in TOP_K_LIST]
                    + [f"{m['MRR']:.4f}", f"{m['NDCG@5']:.4f}"])

    with open(os.path.join(METRICS_DIR, "retrieval.csv"), "w", newline="",
              encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    # latency
    rows2 = [["模式", "P50_ms", "P95_ms", "Mean_ms"]]
    for mode in EVAL_MODES:
        l = latency[mode]
        rows2.append([mode, f"{l['P50']:.1f}", f"{l['P95']:.1f}",
                       f"{l['mean']:.1f}"])

    with open(os.path.join(METRICS_DIR, "latency.csv"), "w", newline="",
              encoding="utf-8") as f:
        csv.writer(f).writerows(rows2)


def main():
    print("加载数据...")
    queries_data, results = load_data()
    print("计算指标...")
    metrics = compute(queries_data, results)
    latency = compute_latency(results)
    print("保存 CSV...")
    save_csv(metrics, latency)

    print("\n=== 检索指标 ===")
    header = f"{'模式':<16}" + "".join(
        f"{'R@'+str(k):>10}" for k in TOP_K_LIST) \
        + f"{'P@3':>10}{'MRR':>10}{'NDCG@5':>10}"
    print(header)
    for mode in EVAL_MODES:
        m = metrics[mode]
        print(f"{mode:<16}" + "".join(
            f"{m[f'Recall@{k}']:>10.4f}" for k in TOP_K_LIST)
              + f"{m['Precision@3']:>10.4f}{m['MRR']:>10.4f}"
                f"{m['NDCG@5']:>10.4f}")

    print("\n=== 延迟 (ms) ===")
    print(f"{'模式':<16}{'P50':>10}{'P95':>10}{'Mean':>10}")
    for mode in EVAL_MODES:
        l = latency[mode]
        print(f"{mode:<16}{l['P50']:>10.1f}{l['P95']:>10.1f}{l['mean']:>10.1f}")

    print(f"\nCSV → {METRICS_DIR}/")


if __name__ == "__main__":
    main()
