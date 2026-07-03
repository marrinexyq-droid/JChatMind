from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.evaluation.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k


@dataclass(frozen=True)
class CaseInventory:
    total_cases: int
    split_counts: dict[str, int]
    tactic_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    source_counts: dict[str, int]


@dataclass(frozen=True)
class RetrievalGroupMetrics:
    run_id: str
    mode: str
    sample_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    precision_at_1: float
    mrr: float
    ndcg_at_5: float


@dataclass(frozen=True)
class RagasCaseEvaluation:
    inventory: CaseInventory
    retrieval_metrics: list[RetrievalGroupMetrics]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def summarize_cases(cases: Iterable[dict[str, Any]]) -> CaseInventory:
    rows = list(cases)
    return CaseInventory(
        total_cases=len(rows),
        split_counts=dict(sorted(Counter(row["dataset_split"] for row in rows).items())),
        tactic_counts=dict(sorted(Counter(row["tactic"] for row in rows).items())),
        difficulty_counts=dict(sorted(Counter(row["difficulty"] for row in rows).items())),
        source_counts=dict(
            sorted(Counter(row["quality"]["source"] for row in rows).items())
        ),
    )


def evaluate_retrieval_observations(
    observations: Iterable[dict[str, Any]],
) -> list[RetrievalGroupMetrics]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        if row["dataset_split"] != "legacy_retrieval_observation":
            continue
        source_ref = row["source_refs"][0]
        grouped[(str(source_ref["run_id"]), str(source_ref["mode"]))].append(row)

    metrics: list[RetrievalGroupMetrics] = []
    for (run_id, mode), rows in sorted(grouped.items()):
        recall_1 = []
        recall_3 = []
        recall_5 = []
        recall_10 = []
        precision_1 = []
        reciprocal_ranks = []
        ndcg_5 = []

        for row in rows:
            truth = list(row["ground_truth_context_ids"])
            retrieved = list(row["retrieved_context_ids"])
            recall_1.append(recall_at_k(truth, retrieved, 1))
            recall_3.append(recall_at_k(truth, retrieved, 3))
            recall_5.append(recall_at_k(truth, retrieved, 5))
            recall_10.append(recall_at_k(truth, retrieved, 10))
            precision_1.append(precision_at_k(truth, retrieved, 1))
            reciprocal_ranks.append(mrr(truth, retrieved))
            ndcg_5.append(ndcg_at_k(truth, retrieved, 5))

        metrics.append(
            RetrievalGroupMetrics(
                run_id=run_id,
                mode=mode,
                sample_count=len(rows),
                recall_at_1=mean(recall_1),
                recall_at_3=mean(recall_3),
                recall_at_5=mean(recall_5),
                recall_at_10=mean(recall_10),
                precision_at_1=mean(precision_1),
                mrr=mean(reciprocal_ranks),
                ndcg_at_5=mean(ndcg_5),
            )
        )
    return metrics


def evaluate_dataset(dataset_dir: Path) -> RagasCaseEvaluation:
    combined = load_jsonl(dataset_dir / "ragas_cases.combined.jsonl")
    observations = [
        row
        for row in combined
        if row["dataset_split"] == "legacy_retrieval_observation"
    ]
    return RagasCaseEvaluation(
        inventory=summarize_cases(combined),
        retrieval_metrics=evaluate_retrieval_observations(observations),
    )


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def as_report_dict(evaluation: RagasCaseEvaluation) -> dict[str, Any]:
    return {
        "inventory": {
            "total_cases": evaluation.inventory.total_cases,
            "split_counts": evaluation.inventory.split_counts,
            "tactic_counts": evaluation.inventory.tactic_counts,
            "difficulty_counts": evaluation.inventory.difficulty_counts,
            "source_counts": evaluation.inventory.source_counts,
        },
        "retrieval_metrics": [
            {
                "run_id": row.run_id,
                "mode": row.mode,
                "sample_count": row.sample_count,
                "recall_at_1": round(row.recall_at_1, 4),
                "recall_at_3": round(row.recall_at_3, 4),
                "recall_at_5": round(row.recall_at_5, 4),
                "recall_at_10": round(row.recall_at_10, 4),
                "precision_at_1": round(row.precision_at_1, 4),
                "mrr": round(row.mrr, 4),
                "ndcg_at_5": round(row.ndcg_at_5, 4),
            }
            for row in evaluation.retrieval_metrics
        ],
    }
