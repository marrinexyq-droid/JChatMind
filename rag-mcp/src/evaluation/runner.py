from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.evaluation.ragas_selftest import check_ragas_available


@dataclass(frozen=True)
class EvaluationSummary:
    baseline_report_exists: bool
    baseline_report_path: str
    ragas_available: bool
    ragas_message: str


def summarize_environment(baseline_report: Path) -> EvaluationSummary:
    ragas_status = check_ragas_available()
    return EvaluationSummary(
        baseline_report_exists=baseline_report.exists(),
        baseline_report_path=str(baseline_report),
        ragas_available=bool(ragas_status["available"]),
        ragas_message=str(ragas_status["message"]),
    )
