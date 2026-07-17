from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.ragas_judged import (
    DeterministicJudgeClient,
    JudgeThresholds,
    build_configured_judge,
    evaluate_judged_ragas,
    load_answer_generation_cases,
    load_judge_config,
    not_configured_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the judge-model RAGAS gate for answer generation cases."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "evaluation",
        help="Directory containing ragas_cases.combined.jsonl.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum cases to judge. Keep this small for paid remote judges.",
    )
    parser.add_argument(
        "--answer-policy",
        choices=["generated", "reference"],
        default="reference",
        help="Use generated answers only, or reference answers for judge harness smoke.",
    )
    parser.add_argument(
        "--pipeline-report",
        type=Path,
        help="Current-pipeline JSON report required by --answer-policy generated.",
    )
    parser.add_argument(
        "--mock-judge",
        action="store_true",
        help="Use deterministic offline scoring instead of a configured model judge.",
    )
    parser.add_argument("--min-faithfulness", type=float, default=0.7)
    parser.add_argument("--min-answer-relevancy", type=float, default=0.7)
    parser.add_argument("--min-case-score", type=float, default=0.5)
    parser.add_argument(
        "--allow-not-configured",
        action="store_true",
        help="Return zero when judge credentials are missing.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path for a JSON report.",
    )
    args = parser.parse_args()

    if args.mock_judge:
        judge = DeterministicJudgeClient()
    else:
        config, missing = load_judge_config()
        if missing:
            report = not_configured_report(missing)
            write_report(args.output_json, report)
            print_summary(report)
            return 0 if args.allow_not_configured else 1
        assert config is not None
        judge = build_configured_judge(config)

    cases = load_answer_generation_cases(
        args.dataset_dir,
        limit=args.limit,
        answer_policy=args.answer_policy,
        pipeline_report=args.pipeline_report,
    )
    thresholds = JudgeThresholds(
        min_mean_faithfulness=args.min_faithfulness,
        min_mean_answer_relevancy=args.min_answer_relevancy,
        min_case_score=args.min_case_score,
    )
    try:
        report = evaluate_judged_ragas(cases, judge, thresholds=thresholds)
    except Exception as exc:
        report = {
            "version": "2.5",
            "status": "judge_error",
            "judge": {"provider": judge.provider, "model": judge.model},
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_report(args.output_json, report)
        print_summary(report)
        return 1
    report["dataset"] = {
        "dataset_dir": str(args.dataset_dir),
        "answer_policy": args.answer_policy,
        "pipeline_report": (
            str(args.pipeline_report) if args.pipeline_report is not None else None
        ),
        "limit": args.limit,
    }
    write_report(args.output_json, report)
    print_summary(report)
    return 0 if report["status"] == "passed" else 1


def write_report(output_json: Path | None, report: dict) -> None:
    if output_json is None:
        return
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def print_summary(report: dict) -> None:
    print("RAGAS judged answer-generation gate")
    print(f"status={report['status']}")
    if report["status"] == "judge_error":
        print(f"judge={report['judge']['provider']}/{report['judge']['model']}")
        print(f"error_type={report['error_type']}")
        return
    if report["status"] == "not_configured":
        print(f"missing={','.join(report['missing'])}")
        return

    print(f"case_count={report['case_count']}")
    print(f"judge={report['judge']['provider']}/{report['judge']['model']}")
    metrics = report["metrics"]
    print(f"faithfulness.mean={metrics['faithfulness']['mean']:.4f}")
    print(f"answer_relevancy.mean={metrics['answer_relevancy']['mean']:.4f}")
    if report.get("failed_cases"):
        print(f"failed_cases={','.join(report['failed_cases'])}")


if __name__ == "__main__":
    raise SystemExit(main())
