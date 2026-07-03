from __future__ import annotations

from pathlib import Path

from src.evaluation.ragas_cases import (
    as_report_dict,
    evaluate_dataset,
    evaluate_retrieval_observations,
    summarize_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "data" / "evaluation"


def test_summarize_cases_counts_inventory_dimensions():
    cases = [
        {
            "dataset_split": "gold_retrieval",
            "tactic": "hypothetical_question",
            "difficulty": "easy",
            "quality": {"source": "legacy_queries_json"},
        },
        {
            "dataset_split": "answer_generation",
            "tactic": "section_summary",
            "difficulty": "medium",
            "quality": {"source": "clean_markdown_section"},
        },
    ]

    inventory = summarize_cases(cases)

    assert inventory.total_cases == 2
    assert inventory.split_counts == {"answer_generation": 1, "gold_retrieval": 1}
    assert inventory.tactic_counts["section_summary"] == 1
    assert inventory.difficulty_counts["easy"] == 1
    assert inventory.source_counts["legacy_queries_json"] == 1


def test_evaluate_retrieval_observations_groups_by_run_and_mode():
    rows = [
        {
            "dataset_split": "legacy_retrieval_observation",
            "ground_truth_context_ids": ["a"],
            "retrieved_context_ids": ["a", "b", "c"],
            "source_refs": [{"run_id": "baseline", "mode": "hybrid"}],
        },
        {
            "dataset_split": "legacy_retrieval_observation",
            "ground_truth_context_ids": ["z"],
            "retrieved_context_ids": ["a", "z", "c"],
            "source_refs": [{"run_id": "baseline", "mode": "hybrid"}],
        },
    ]

    metrics = evaluate_retrieval_observations(rows)

    assert len(metrics) == 1
    assert metrics[0].sample_count == 2
    assert metrics[0].recall_at_1 == 0.5
    assert metrics[0].recall_at_3 == 1.0
    assert metrics[0].precision_at_1 == 0.5
    assert metrics[0].mrr == 0.75


def test_evaluate_dataset_reports_strict_battle_dataset_metrics():
    report = as_report_dict(evaluate_dataset(DATASET_DIR))

    assert report["inventory"]["total_cases"] == 1014
    assert report["inventory"]["split_counts"]["gold_retrieval"] == 58
    assert report["inventory"]["split_counts"]["legacy_retrieval_observation"] == 774
    assert report["inventory"]["split_counts"]["answer_generation"] >= 180
    assert len(report["retrieval_metrics"]) == 15
    assert {row["mode"] for row in report["retrieval_metrics"]} == {
        "hybrid",
        "hybrid-rerank",
        "vector",
    }
    assert all(row["sample_count"] in {30, 57} for row in report["retrieval_metrics"])
