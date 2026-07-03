from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "data" / "evaluation"


def load_jsonl(name: str) -> list[dict]:
    path = DATASET_DIR / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ragas_case_files_match_manifest_counts():
    manifest = json.loads(
        (DATASET_DIR / "ragas_cases_manifest.json").read_text(encoding="utf-8")
    )

    gold = load_jsonl("gold_retrieval_cases.jsonl")
    observations = load_jsonl("legacy_retrieval_observations.jsonl")
    answer = load_jsonl("answer_generation_cases.jsonl")
    combined = load_jsonl("ragas_cases.combined.jsonl")

    assert manifest["counts"]["gold_retrieval_cases"] == 58
    assert manifest["counts"]["legacy_retrieval_observations"] == 774
    assert manifest["counts"]["answer_generation_cases"] >= 180
    assert manifest["counts"]["total_records"] == len(combined)
    assert len(gold) + len(observations) + len(answer) == len(combined)


def test_ragas_cases_have_required_traceable_fields():
    required = {
        "case_id",
        "dataset_split",
        "question",
        "answer",
        "contexts",
        "ground_truth",
        "reference_contexts",
        "ground_truth_context_ids",
        "collection",
        "tags",
        "difficulty",
        "expected_answer_type",
        "tactic",
        "source_refs",
        "quality",
    }
    combined = load_jsonl("ragas_cases.combined.jsonl")
    case_ids = [record["case_id"] for record in combined]

    assert len(case_ids) == len(set(case_ids))
    for record in combined:
        assert required.issubset(record)
        assert record["question"].strip()
        assert len(record["ground_truth"]) >= 20
        assert record["ground_truth_context_ids"]
        assert record["source_refs"]
        assert record["quality"]["bad_text_score"] == 0.0


def test_ragas_cases_preserve_split_semantics():
    gold = load_jsonl("gold_retrieval_cases.jsonl")
    observations = load_jsonl("legacy_retrieval_observations.jsonl")
    answer = load_jsonl("answer_generation_cases.jsonl")

    assert all(record["contexts"] == [] for record in gold)
    assert all(record["answer_status"] == "retrieval_only" for record in gold)
    assert all(record["contexts"] for record in observations)
    assert all(record["retrieved_context_ids"] for record in observations)
    assert all(record["answer_status"] == "retrieval_only" for record in observations)
    assert all(len(record["contexts"]) == 1 for record in answer)
    assert all(record["answer_status"] == "to_be_filled_by_eval_runner" for record in answer)


def test_ragas_cases_filter_low_value_or_failed_records():
    combined = load_jsonl("ragas_cases.combined.jsonl")
    questions = [record["question"].lower() for record in combined]
    observation_query_ids = [
        ref["query_id"]
        for record in combined
        for ref in record["source_refs"]
        if "query_id" in ref and record["dataset_split"] == "legacy_retrieval_observation"
    ]

    assert all("assistant" not in question for question in questions)
    assert all(not question.startswith("turn ") for question in questions)
    assert "glm_002" not in observation_query_ids


def test_ragas_cases_cover_multiple_battle_tactics():
    manifest = json.loads(
        (DATASET_DIR / "ragas_cases_manifest.json").read_text(encoding="utf-8")
    )
    tactic_counts = manifest["tactic_counts"]

    assert tactic_counts["retrieval_benchmark_observation"] == 774
    assert tactic_counts["hypothetical_question"] == 30
    assert tactic_counts["generated_llm_question"] == 28
    assert tactic_counts["section_summary"] >= 100
    assert tactic_counts["section_key_items"] >= 50
    assert tactic_counts["failure_mode"] >= 20
