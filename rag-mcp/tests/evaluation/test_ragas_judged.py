from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.evaluate_ragas_judged import write_report
from src.evaluation.ragas_judged import (
    DeterministicJudgeClient,
    JudgeConfig,
    JudgeScore,
    JudgedRagasCase,
    build_configured_judge,
    clamp_score,
    evaluate_judged_ragas,
    load_answer_generation_cases,
    load_judge_config,
    parse_score_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "evaluate_ragas_judged.py"


def write_dataset(root: Path) -> Path:
    dataset_dir = root / "data" / "evaluation"
    dataset_dir.mkdir(parents=True)
    rows = [
        {
            "case_id": "ans-1",
            "dataset_split": "answer_generation",
            "question": "What does RAG add?",
            "answer": "",
            "reference_answer": "RAG adds grounded context and traceable evidence.",
            "ground_truth": "RAG adds grounded context and traceable evidence.",
            "contexts": ["RAG adds grounded context and traceable evidence."],
            "difficulty": "easy",
            "tactic": "section_summary",
        },
        {
            "case_id": "ret-1",
            "dataset_split": "gold_retrieval",
            "question": "ignored",
            "quality": {"source": "fixture"},
            "tactic": "fixture",
            "difficulty": "easy",
        },
    ]
    (dataset_dir / "ragas_cases.combined.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return dataset_dir


def test_load_answer_generation_cases_can_use_reference_answer_fallback(tmp_path):
    dataset_dir = write_dataset(tmp_path)

    cases = load_answer_generation_cases(dataset_dir, answer_policy="reference")

    assert len(cases) == 1
    assert cases[0].case_id == "ans-1"
    assert cases[0].answer_source == "reference_answer_fallback"


def test_generated_answer_policy_requires_current_pipeline_report(tmp_path):
    dataset_dir = write_dataset(tmp_path)

    with pytest.raises(ValueError, match="pipeline_report is required"):
        load_answer_generation_cases(dataset_dir, answer_policy="generated")


def test_generated_policy_reads_answer_and_contexts_from_pipeline_report(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "status": "passed",
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "Live generated answer [C1].",
                        "answer_source": "generated_answer",
                        "retrieved_context_ids": ["chunk-live-1"],
                        "retrieved_contexts": ["Live retrieved evidence."],
                        "error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cases = load_answer_generation_cases(
        dataset_dir,
        answer_policy="generated",
        pipeline_report=pipeline_report,
    )

    assert len(cases) == 1
    assert cases[0].answer == "Live generated answer [C1]."
    assert cases[0].contexts == ["Live retrieved evidence."]
    assert cases[0].answer_source == "generated_answer"


@pytest.mark.parametrize("overflow", ["1e400", "-1e400"])
def test_generated_policy_rejects_overflow_numbers_in_pipeline_report(
    tmp_path,
    overflow,
):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        (
            '{"cases":[{"case_id":"ans-1","answer":"Live generated answer [C1].",'
            '"answer_source":"generated_answer","retrieved_contexts":["Evidence."],'
            f'"latency_ms":{overflow},"error":null}}]}}'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-finite JSON number"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_generated_policy_rejects_reference_answer_fallback(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "Static reference answer.",
                        "answer_source": "reference_answer_fallback",
                        "retrieved_contexts": ["Live evidence."],
                        "error": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reference answer fallback"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_generated_policy_rejects_evidence_fallback(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "Evidence found: [C1]",
                        "answer_source": "evidence_fallback",
                        "retrieved_contexts": ["Live evidence."],
                        "error": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="did not use a generated answer"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_generated_policy_rejects_failed_pipeline_case(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "",
                        "answer_source": "generated_answer",
                        "retrieved_contexts": [],
                        "error": "RuntimeError: model unavailable",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="current pipeline case ans-1 failed"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_generated_policy_rejects_blank_pipeline_answer(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "",
                        "answer_source": "generated_answer",
                        "retrieved_contexts": ["Live evidence."],
                        "error": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="current pipeline case ans-1 has no answer"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_generated_policy_requires_result_for_every_dataset_case(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    pipeline_report.write_text(json.dumps({"cases": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing current pipeline case ans-1"):
        load_answer_generation_cases(
            dataset_dir,
            answer_policy="generated",
            pipeline_report=pipeline_report,
        )


def test_limit_zero_returns_no_cases(tmp_path):
    dataset_dir = write_dataset(tmp_path)

    cases = load_answer_generation_cases(dataset_dir, limit=0)

    assert cases == []


def test_deterministic_judge_passes_grounded_reference_answer():
    cases = [
        JudgedRagasCase(
            case_id="case-1",
            question="What does RAG add?",
            answer="RAG adds grounded context and traceable evidence.",
            contexts=["RAG adds grounded context and traceable evidence."],
            reference_answer="RAG adds grounded context and traceable evidence.",
            difficulty="easy",
            tactic="section_summary",
            answer_source="reference_answer_fallback",
        )
    ]

    report = evaluate_judged_ragas(cases, DeterministicJudgeClient())

    assert report["status"] == "passed"
    assert report["metrics"]["faithfulness"]["mean"] == 1.0
    assert report["metrics"]["answer_relevancy"]["mean"] == 1.0


def test_evaluation_input_sha256_is_stable_and_binds_answer_and_contexts():
    case = JudgedRagasCase(
        case_id="ans-1",
        question="What does RAG add?",
        answer="RAG adds grounded context.",
        contexts=["Retrieved evidence one.", "Retrieved evidence two."],
        reference_answer="RAG adds grounded context.",
        difficulty="easy",
        tactic="section_summary",
        answer_source="generated_answer",
    )
    judge = DeterministicJudgeClient()

    baseline = evaluate_judged_ragas([case], judge)["cases"][0][
        "evaluation_input_sha256"
    ]
    repeated = evaluate_judged_ragas([case], judge)["cases"][0][
        "evaluation_input_sha256"
    ]
    changed_answer = evaluate_judged_ragas(
        [replace(case, answer="RAG adds different grounded context.")],
        judge,
    )["cases"][0]["evaluation_input_sha256"]
    changed_contexts = evaluate_judged_ragas(
        [replace(case, contexts=["Different retrieved evidence."])],
        judge,
    )["cases"][0]["evaluation_input_sha256"]

    assert baseline == "b1f9d2aaa55b754a188ba055924db9a23cbbe46c350c71ab9671c563382629c0"
    assert repeated == baseline
    assert changed_answer != baseline
    assert changed_contexts != baseline


def test_evaluate_judged_ragas_rejects_non_finite_scores_from_any_judge():
    class NonFiniteJudge:
        provider = "test"
        model = "non-finite"

        def judge(self, case):
            return JudgeScore(
                faithfulness=float("nan"),
                answer_relevancy=1.0,
                reason="invalid score",
            )

    cases = [
        JudgedRagasCase(
            case_id="ans-non-finite",
            question="What does RAG add?",
            answer="RAG adds retrieved context.",
            contexts=["RAG retrieves context before generation."],
            reference_answer="RAG adds retrieved context.",
            difficulty="easy",
            tactic="section_summary",
            answer_source="generated_answer",
        )
    ]

    with pytest.raises(ValueError, match="Judge score must be finite"):
        evaluate_judged_ragas(cases, NonFiniteJudge())


def test_load_judge_config_reports_missing_env():
    config, missing = load_judge_config({})

    assert config is None
    assert "RAGAS_JUDGE_PROVIDER" in missing
    assert "RAGAS_JUDGE_API_KEY or GOOGLE_API_KEY" in missing


def test_load_judge_config_accepts_google_key_fallback():
    config, missing = load_judge_config({"GOOGLE_API_KEY": "secret"})

    assert missing == []
    assert config == JudgeConfig(
        provider="google",
        model="gemini-2.5-flash",
        api_key="secret",
    )
    assert build_configured_judge(config).provider == "google"


def test_parse_score_payload_accepts_json_embedded_in_text():
    payload = parse_score_payload(
        'Here is the score: {"faithfulness": 0.8, "answer_relevancy": 0.9, "reason": "ok"}'
    )

    assert payload["faithfulness"] == 0.8
    assert payload["answer_relevancy"] == 0.9


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity"])
def test_parse_score_payload_rejects_non_finite_json_scores(non_finite):
    with pytest.raises(ValueError, match="non-finite JSON number"):
        parse_score_payload(
            f'{{"faithfulness": {non_finite}, "answer_relevancy": 0.9}}'
        )


@pytest.mark.parametrize("overflow", ["1e400", "-1e400"])
def test_parse_score_payload_rejects_overflow_json_scores(overflow):
    with pytest.raises(ValueError, match="non-finite JSON number"):
        parse_score_payload(
            f'{{"faithfulness": {overflow}, "answer_relevancy": 0.9}}'
        )


@pytest.mark.parametrize(
    "non_finite",
    [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity"],
)
def test_clamp_score_rejects_non_finite_values(non_finite):
    with pytest.raises(ValueError, match="Judge score must be finite"):
        clamp_score(non_finite)


@pytest.mark.parametrize("boolean", [True, False])
def test_clamp_score_rejects_boolean_values(boolean):
    with pytest.raises(ValueError, match="Judge score must be a number"):
        clamp_score(boolean)


def test_judged_report_writer_rejects_non_finite_json(tmp_path):
    output_json = tmp_path / "invalid-report.json"

    with pytest.raises(ValueError, match="Out of range float values"):
        write_report(output_json, {"status": "failed", "score": float("nan")})

    assert not output_json.exists()


def test_judged_ragas_cli_writes_mock_report(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    output_json = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset-dir",
            str(dataset_dir),
            "--mock-judge",
            "--limit",
            "1",
            "--output-json",
            str(output_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "status=passed" in result.stdout
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["dataset"]["answer_policy"] == "reference"


def test_judged_ragas_cli_uses_current_pipeline_report_for_generated_policy(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    pipeline_report = tmp_path / "current-pipeline.json"
    output_json = tmp_path / "generated-report.json"
    pipeline_report.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "ans-1",
                        "answer": "RAG adds grounded context and traceable evidence [C1].",
                        "answer_source": "generated_answer",
                        "retrieved_contexts": [
                            "RAG adds grounded context and traceable evidence."
                        ],
                        "error": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset-dir",
            str(dataset_dir),
            "--answer-policy",
            "generated",
            "--pipeline-report",
            str(pipeline_report),
            "--mock-judge",
            "--limit",
            "1",
            "--output-json",
            str(output_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["dataset"]["pipeline_report"] == str(pipeline_report)
    assert report["cases"][0]["answer_source"] == "generated_answer"


def test_judged_ragas_cli_reports_not_configured_without_mock(tmp_path):
    dataset_dir = write_dataset(tmp_path)
    output_json = tmp_path / "not_configured.json"
    env = os.environ.copy()
    for key in [
        "RAGAS_JUDGE_PROVIDER",
        "RAGAS_JUDGE_MODEL",
        "RAGAS_JUDGE_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_MODEL",
    ]:
        env.pop(key, None)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset-dir",
            str(dataset_dir),
            "--allow-not-configured",
            "--output-json",
            str(output_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "status=not_configured" in result.stdout
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "not_configured"
    assert "RAGAS_JUDGE_API_KEY or GOOGLE_API_KEY" in report["missing"]
