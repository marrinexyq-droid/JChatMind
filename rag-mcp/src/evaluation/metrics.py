from __future__ import annotations

import math


def recall_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    if not ground_truth:
        return 0.0
    hits = sum(1 for item in ground_truth if item in set(retrieved[:k]))
    return hits / len(ground_truth)


def precision_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in set(ground_truth))
    return hits / k


def mrr(ground_truth: list[str], retrieved: list[str]) -> float:
    truth = set(ground_truth)
    for index, item in enumerate(retrieved):
        if item in truth:
            return 1.0 / (index + 1)
    return 0.0


def ndcg_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    truth = set(ground_truth)
    dcg = 0.0
    for index, item in enumerate(retrieved[:k]):
        relevance = 1.0 if item in truth else 0.0
        dcg += relevance / math.log2(index + 2)
    ideal_count = min(len(truth), k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_count))
    return dcg / idcg if idcg else 0.0
