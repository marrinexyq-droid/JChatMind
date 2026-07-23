from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.canary_smoke import run_canary
from scripts.evaluate_current_pipeline import run_current_pipeline
from src.evaluation.ragas_cases import as_report_dict, evaluate_dataset
from src.evaluation.pipeline_runner import (
    MATCH_METADATA_FIELDS,
    RETRIEVAL_EVALUATOR_CONTRACT,
    VERSION as PIPELINE_REPORT_VERSION,
)
from src.evaluation.ragas_judged import (
    build_configured_judge,
    evaluate_judged_ragas,
    load_answer_generation_cases,
    load_judge_config,
    not_configured_report,
)


DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "evaluation"
DEFAULT_JAVA_HYBRID_RECALL_AT_1 = 0.9298
DEFAULT_JAVA_HYBRID_MRR = 0.9649
DEFAULT_MAX_DEGRADATION = 0.02
DEFAULT_MAX_P95_LATENCY_MS = 8000.0
DEFAULT_MAX_FALLBACK_RATE = 0.01
DEFAULT_MAX_ERROR_RATE = 0.01
DEFAULT_JAVA_BASELINE_REPORT = Path(
    "data/evaluation/java_current_pipeline_baseline.json"
)
JAVA_BASELINE_PRODUCER = "jchatmind-java-current-pipeline-evaluator"
JAVA_BASELINE_RUNTIME_SCOPE = "java_rag_retrieval"


def run_acceptance(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_json: Path | None = None,
    collection: str = "acceptance-canary",
    run_smoke: bool = True,
    ragas_rounds: int = 3,
    min_total_cases: int = 1000,
    gate_run_id: str = "k120",
    gate_mode: str = "hybrid-rerank",
    min_mrr: float = 0.95,
    min_precision_at_1: float = 0.90,
    min_recall_at_1: float = 0.90,
    java_baseline_recall_at_1: float = DEFAULT_JAVA_HYBRID_RECALL_AT_1,
    java_baseline_mrr: float = DEFAULT_JAVA_HYBRID_MRR,
    max_degradation: float = DEFAULT_MAX_DEGRADATION,
    max_p95_latency_ms: float = DEFAULT_MAX_P95_LATENCY_MS,
    max_fallback_rate: float = DEFAULT_MAX_FALLBACK_RATE,
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
    java_baseline_report_path: Path | None = None,
    require_chroma: bool = False,
    current_pipeline: bool = False,
    answer_policy: str = "reference",
) -> dict[str, Any]:
    if ragas_rounds < 1:
        raise ValueError("ragas_rounds must be at least 1")
    if answer_policy not in {"generated", "reference"}:
        raise ValueError("answer_policy must be 'generated' or 'reference'")
    if answer_policy == "generated" and not current_pipeline:
        raise ValueError("answer_policy 'generated' requires current_pipeline=True")
    _validate_acceptance_thresholds(
        min_mrr=min_mrr,
        min_precision_at_1=min_precision_at_1,
        min_recall_at_1=min_recall_at_1,
        java_baseline_recall_at_1=java_baseline_recall_at_1,
        java_baseline_mrr=java_baseline_mrr,
        max_degradation=max_degradation,
        max_p95_latency_ms=max_p95_latency_ms,
        max_fallback_rate=max_fallback_rate,
        max_error_rate=max_error_rate,
    )

    canary_report = None
    canary_error = None
    if run_smoke:
        try:
            canary_report = _run_smoke_canary(collection, require_chroma=require_chroma)
        except Exception as exc:
            canary_error = str(exc)
    ragas_reports = []
    ragas_error = None
    try:
        ragas_reports = [
            _evaluate_ragas_round(dataset_dir, index + 1)
            for index in range(ragas_rounds)
        ]
    except Exception as exc:
        ragas_error = f"{type(exc).__name__}: {exc}"
    current_pipeline_report = None
    current_pipeline_error = None
    current_pipeline_judge_report = None
    current_pipeline_judge_error = None
    java_baseline_report = None
    java_baseline_report_error = None
    if current_pipeline:
        try:
            current_pipeline_report = _run_current_pipeline(dataset_dir, collection)
        except Exception as exc:
            current_pipeline_error = str(exc)
        if answer_policy == "generated" and current_pipeline_report is not None:
            try:
                current_pipeline_judge_report = _run_current_pipeline_judge(
                    dataset_dir,
                    current_pipeline_report,
                )
            except Exception as exc:
                current_pipeline_judge_error = str(exc)
        if java_baseline_report_path is not None:
            try:
                java_baseline_report = _load_java_baseline_report(
                    java_baseline_report_path
                )
            except Exception as exc:
                java_baseline_report_error = f"{type(exc).__name__}: {exc}"
    report = _build_report(
        canary_report=canary_report,
        canary_error=canary_error,
        smoke_skipped=not run_smoke,
        ragas_reports=ragas_reports,
        ragas_error=ragas_error,
        min_total_cases=min_total_cases,
        gate_run_id=gate_run_id,
        gate_mode=gate_mode,
        min_mrr=min_mrr,
        min_precision_at_1=min_precision_at_1,
        min_recall_at_1=min_recall_at_1,
        java_baseline_recall_at_1=java_baseline_recall_at_1,
        java_baseline_mrr=java_baseline_mrr,
        max_degradation=max_degradation,
        max_p95_latency_ms=max_p95_latency_ms,
        max_fallback_rate=max_fallback_rate,
        max_error_rate=max_error_rate,
        java_baseline_required=java_baseline_report_path is not None,
        java_baseline_report=java_baseline_report,
        java_baseline_report_error=java_baseline_report_error,
        require_chroma=require_chroma,
        current_pipeline=current_pipeline,
        answer_policy=answer_policy,
        current_pipeline_report=current_pipeline_report,
        current_pipeline_error=current_pipeline_error,
        current_pipeline_judge_report=current_pipeline_judge_report,
        current_pipeline_judge_error=current_pipeline_judge_error,
    )

    if output_json is not None:
        serialized_report = _serialize_report(report)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(serialized_report, encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Run the rag-mcp canary acceptance gate."
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--collection", default="acceptance-canary")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--ragas-rounds", type=int, default=3)
    parser.add_argument("--min-total-cases", type=int, default=1000)
    parser.add_argument("--gate-run-id", default="k120")
    parser.add_argument("--gate-mode", default="hybrid-rerank")
    parser.add_argument("--min-mrr", type=float, default=0.95)
    parser.add_argument("--min-precision-at-1", type=float, default=0.90)
    parser.add_argument("--min-recall-at-1", type=float, default=0.90)
    parser.add_argument(
        "--java-baseline-recall-at-1",
        type=float,
        default=DEFAULT_JAVA_HYBRID_RECALL_AT_1,
    )
    parser.add_argument(
        "--java-baseline-mrr",
        type=float,
        default=DEFAULT_JAVA_HYBRID_MRR,
    )
    parser.add_argument(
        "--max-retrieval-degradation",
        dest="max_degradation",
        type=float,
        default=DEFAULT_MAX_DEGRADATION,
    )
    parser.add_argument(
        "--max-p95-latency-ms",
        type=float,
        default=DEFAULT_MAX_P95_LATENCY_MS,
    )
    parser.add_argument(
        "--max-fallback-rate",
        type=float,
        default=DEFAULT_MAX_FALLBACK_RATE,
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=DEFAULT_MAX_ERROR_RATE,
    )
    parser.add_argument("--java-baseline-report", type=Path)
    parser.add_argument("--require-chroma", action="store_true")
    parser.add_argument("--current-pipeline", action="store_true")
    parser.add_argument(
        "--answer-policy",
        choices=["generated", "reference"],
        default="reference",
    )
    args = parser.parse_args(argv)
    if args.answer_policy == "generated" and not args.current_pipeline:
        parser.error("--answer-policy generated requires --current-pipeline")

    report = run_acceptance(
        dataset_dir=args.dataset_dir,
        output_json=args.output_json,
        collection=args.collection,
        run_smoke=not args.skip_smoke,
        ragas_rounds=args.ragas_rounds,
        min_total_cases=args.min_total_cases,
        gate_run_id=args.gate_run_id,
        gate_mode=args.gate_mode,
        min_mrr=args.min_mrr,
        min_precision_at_1=args.min_precision_at_1,
        min_recall_at_1=args.min_recall_at_1,
        java_baseline_recall_at_1=args.java_baseline_recall_at_1,
        java_baseline_mrr=args.java_baseline_mrr,
        max_degradation=args.max_degradation,
        max_p95_latency_ms=args.max_p95_latency_ms,
        max_fallback_rate=args.max_fallback_rate,
        max_error_rate=args.max_error_rate,
        java_baseline_report_path=args.java_baseline_report,
        require_chroma=args.require_chroma,
        current_pipeline=args.current_pipeline,
        answer_policy=args.answer_policy,
    )
    print(_serialize_report(report), end="")
    return 0 if report["status"] == "passed" else 1


def _run_smoke_canary(collection: str, *, require_chroma: bool) -> dict[str, Any]:
    workdir = Path(tempfile.mkdtemp(prefix="rag-mcp-acceptance-"))
    try:
        return run_canary(workdir, collection=collection, require_chroma=require_chroma)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _evaluate_ragas_round(dataset_dir: Path, round_number: int) -> dict[str, Any]:
    report = as_report_dict(evaluate_dataset(dataset_dir))
    return {
        "round": round_number,
        "sha256": _report_sha256(report),
        "report": report,
    }


def _run_current_pipeline(dataset_dir: Path, collection: str) -> dict[str, Any]:
    return run_current_pipeline(
        project_root=PROJECT_ROOT,
        dataset_dir=dataset_dir,
        collection=collection,
        require_indexed_collection=True,
    )


def _run_current_pipeline_judge(
    dataset_dir: Path,
    pipeline_report: dict[str, Any],
) -> dict[str, Any]:
    config, missing = load_judge_config()
    if missing:
        return not_configured_report(missing)
    assert config is not None
    judge = build_configured_judge(config)
    cases = load_answer_generation_cases(
        dataset_dir,
        limit=None,
        answer_policy="generated",
        pipeline_report_data=pipeline_report,
    )
    return evaluate_judged_ragas(cases, judge)


def _load_java_baseline_report(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_non_finite_json,
        parse_float=_parse_finite_float,
    )
    if not isinstance(payload, dict):
        raise ValueError("Java baseline report must be a JSON object")
    return payload


def _build_report(
    *,
    canary_report: dict[str, Any] | None,
    canary_error: str | None,
    smoke_skipped: bool,
    ragas_reports: list[dict[str, Any]],
    ragas_error: str | None,
    min_total_cases: int,
    gate_run_id: str,
    gate_mode: str,
    min_mrr: float,
    min_precision_at_1: float,
    min_recall_at_1: float,
    java_baseline_recall_at_1: float,
    java_baseline_mrr: float,
    max_degradation: float,
    max_p95_latency_ms: float,
    max_fallback_rate: float,
    max_error_rate: float,
    java_baseline_required: bool,
    java_baseline_report: dict[str, Any] | None,
    java_baseline_report_error: str | None,
    require_chroma: bool,
    current_pipeline: bool,
    answer_policy: str,
    current_pipeline_report: dict[str, Any] | None,
    current_pipeline_error: str | None,
    current_pipeline_judge_report: dict[str, Any] | None,
    current_pipeline_judge_error: str | None,
) -> dict[str, Any]:
    first_report = (
        ragas_reports[0]["report"]
        if ragas_reports
        else {"inventory": {"total_cases": 0}, "retrieval_metrics": []}
    )
    hashes = [row["sha256"] for row in ragas_reports]
    stable = bool(hashes) and ragas_error is None and len(set(hashes)) == 1
    target_metric = _find_metric(first_report, gate_run_id, gate_mode)
    gates = [
        _gate(
            "canary_smoke",
            canary_report is not None or smoke_skipped,
            observed=canary_error,
            skipped=smoke_skipped,
        ),
        _gate("ragas_rounds_stable", stable, observed=len(set(hashes)), threshold=1),
        _gate(
            "ragas_total_cases",
            first_report["inventory"]["total_cases"] >= min_total_cases,
            observed=first_report["inventory"]["total_cases"],
            threshold=min_total_cases,
        ),
        _gate(
            "target_metric_present",
            target_metric is not None,
            observed=f"{gate_run_id}/{gate_mode}",
        ),
    ]
    if require_chroma:
        actual_backend = None
        if canary_report is not None:
            actual_backend = (canary_report.get("vector_store") or {}).get("actual_backend")
        gates.append(
            _gate(
                "chroma_vector_store_runtime",
                actual_backend == "ChromaVectorStore",
                observed=actual_backend or canary_error,
                threshold="ChromaVectorStore",
                skipped=smoke_skipped,
            )
        )
    if target_metric is not None:
        gates.extend(
            [
                _gate(
                    "target_mrr",
                    target_metric["mrr"] >= min_mrr,
                    observed=target_metric["mrr"],
                    threshold=min_mrr,
                ),
                _gate(
                    "target_precision_at_1",
                    target_metric["precision_at_1"] >= min_precision_at_1,
                    observed=target_metric["precision_at_1"],
                    threshold=min_precision_at_1,
                ),
            ]
        )
    if current_pipeline:
        pipeline_cases = (
            current_pipeline_report.get("cases", [])
            if current_pipeline_report is not None
            else []
        )
        case_errors = [case for case in pipeline_cases if case.get("error")]
        empty_answers = [
            case for case in pipeline_cases if not str(case.get("answer") or "").strip()
        ]
        reference_fallbacks = [
            case
            for case in pipeline_cases
            if case.get("answer_source") == "reference_answer_fallback"
        ]
        non_generated_answers = [
            case
            for case in pipeline_cases
            if case.get("answer_source") != "generated_answer"
        ]
        actual_backend = (
            current_pipeline_report.get("vector_store_backend")
            if current_pipeline_report is not None
            else None
        )
        retrieval_metrics = (
            current_pipeline_report.get("retrieval_metrics") or {}
            if current_pipeline_report is not None
            else {}
        )
        current_recall_at_1 = retrieval_metrics.get("recall_at_1")
        current_mrr = retrieval_metrics.get("mrr")
        runtime_metrics = (
            current_pipeline_report.get("runtime_metrics") or {}
            if current_pipeline_report is not None
            else {}
        )
        current_p95_latency_ms = runtime_metrics.get("p95_latency_ms")
        current_fallback_rate = runtime_metrics.get("fallback_rate")
        current_error_rate = runtime_metrics.get("error_rate")
        pipeline_dataset = (
            current_pipeline_report.get("dataset") or {}
            if current_pipeline_report is not None
            else {}
        )
        baseline_dataset = (
            java_baseline_report.get("dataset") or {}
            if java_baseline_report is not None
            else {}
        )
        baseline_retrieval_metrics = (
            java_baseline_report.get("retrieval_metrics") or {}
            if java_baseline_report is not None
            else {}
        )
        pipeline_case_evidence = _recomputed_retrieval_evidence(
            current_pipeline_report
        )
        baseline_case_evidence = _recomputed_retrieval_evidence(
            java_baseline_report
        )
        pipeline_evaluator = (
            current_pipeline_report.get("evaluator")
            if current_pipeline_report is not None
            else None
        )
        baseline_evaluator = (
            java_baseline_report.get("evaluator")
            if java_baseline_report is not None
            else None
        )
        pipeline_top_k = (
            current_pipeline_report.get("top_k")
            if current_pipeline_report is not None
            else None
        )
        baseline_top_k = (
            java_baseline_report.get("top_k")
            if java_baseline_report is not None
            else None
        )
        comparable_java_baseline = (
            java_baseline_report is not None
            and java_baseline_report.get("version")
            == PIPELINE_REPORT_VERSION
            and current_pipeline_report is not None
            and current_pipeline_report.get("version")
            == PIPELINE_REPORT_VERSION
            and _valid_java_baseline_provenance(java_baseline_report)
            and java_baseline_report.get("status") == "passed"
            and java_baseline_report.get("mode")
            == (
                current_pipeline_report.get("mode")
                if current_pipeline_report is not None
                else None
            )
            and baseline_dataset == pipeline_dataset
            and _valid_dataset_contract(pipeline_dataset)
            and _is_positive_int(pipeline_top_k)
            and baseline_top_k == pipeline_top_k
            and pipeline_evaluator == RETRIEVAL_EVALUATOR_CONTRACT
            and baseline_evaluator == RETRIEVAL_EVALUATOR_CONTRACT
            and pipeline_case_evidence is not None
            and baseline_case_evidence is not None
            and pipeline_case_evidence["case_signatures"]
            == baseline_case_evidence["case_signatures"]
            and _retrieval_summary_matches(
                retrieval_metrics,
                pipeline_case_evidence,
            )
            and _retrieval_summary_matches(
                baseline_retrieval_metrics,
                baseline_case_evidence,
            )
        )
        if comparable_java_baseline:
            java_baseline_recall_at_1 = baseline_retrieval_metrics["recall_at_1"]
            java_baseline_mrr = baseline_retrieval_metrics["mrr"]
        if java_baseline_required:
            gates.append(
                _gate(
                    "current_pipeline_java_baseline_comparable",
                    comparable_java_baseline,
                    observed={
                        "pipeline_dataset": pipeline_dataset,
                        "java_dataset": baseline_dataset,
                        "pipeline_mode": (
                            current_pipeline_report.get("mode")
                            if current_pipeline_report is not None
                            else None
                        ),
                        "java_mode": (
                            java_baseline_report.get("mode")
                            if java_baseline_report is not None
                            else None
                        ),
                        "pipeline_top_k": pipeline_top_k,
                        "java_top_k": baseline_top_k,
                        "pipeline_evaluator": pipeline_evaluator,
                        "java_evaluator": baseline_evaluator,
                        "pipeline_case_evidence": pipeline_case_evidence,
                        "java_case_evidence": baseline_case_evidence,
                        "error": java_baseline_report_error,
                    },
                    threshold=(
                        "same semantic cohort, case evidence, retrieval mode, "
                        "top_k, and evaluator contract"
                    ),
                )
            )
        gates.extend(
            [
                _gate(
                    "current_pipeline_report_passed",
                    current_pipeline_report is not None
                    and current_pipeline_report.get("status") == "passed",
                    observed=(
                        current_pipeline_report.get("status")
                        if current_pipeline_report is not None
                        else current_pipeline_error
                    ),
                    threshold="passed",
                ),
                _gate(
                    "current_pipeline_executed",
                    current_pipeline_report is not None,
                    observed=current_pipeline_error,
                ),
                _gate(
                    "current_pipeline_generated_answers",
                    current_pipeline_report is not None
                    and answer_policy == "generated"
                    and not non_generated_answers,
                    observed={
                        "answer_policy": answer_policy,
                        "non_generated_count": len(non_generated_answers),
                    },
                    threshold={
                        "answer_policy": "generated",
                        "non_generated_count": 0,
                    },
                ),
                _gate(
                    "current_pipeline_cases_present",
                    current_pipeline_report is not None and bool(pipeline_cases),
                    observed=len(pipeline_cases),
                    threshold=">=1",
                ),
                _gate(
                    "current_pipeline_no_case_errors",
                    current_pipeline_report is not None and not case_errors,
                    observed=len(case_errors),
                    threshold=0,
                ),
                _gate(
                    "current_pipeline_nonempty_answers",
                    current_pipeline_report is not None and not empty_answers,
                    observed=len(empty_answers),
                    threshold=0,
                ),
                _gate(
                    "current_pipeline_no_reference_fallback",
                    current_pipeline_report is not None and not reference_fallbacks,
                    observed=len(reference_fallbacks),
                    threshold=0,
                ),
                _gate(
                    "current_pipeline_chroma_backend",
                    actual_backend == "ChromaVectorStore",
                    observed=actual_backend or current_pipeline_error,
                    threshold="ChromaVectorStore",
                ),
                _gate(
                    "current_pipeline_recall_at_1",
                    _is_finite_number(current_recall_at_1)
                    and current_recall_at_1 >= min_recall_at_1,
                    observed=current_recall_at_1,
                    threshold=min_recall_at_1,
                ),
                _gate(
                    "current_pipeline_recall_at_1_degradation",
                    _is_finite_number(current_recall_at_1)
                    and current_recall_at_1
                    >= java_baseline_recall_at_1 - max_degradation,
                    observed=current_recall_at_1,
                    threshold={
                        "baseline": java_baseline_recall_at_1,
                        "max_degradation": max_degradation,
                        "minimum": java_baseline_recall_at_1 - max_degradation,
                    },
                ),
                _gate(
                    "current_pipeline_mrr",
                    _is_finite_number(current_mrr)
                    and current_mrr >= min_mrr,
                    observed=current_mrr,
                    threshold=min_mrr,
                ),
                _gate(
                    "current_pipeline_mrr_degradation",
                    _is_finite_number(current_mrr)
                    and current_mrr >= java_baseline_mrr - max_degradation,
                    observed=current_mrr,
                    threshold={
                        "baseline": java_baseline_mrr,
                        "max_degradation": max_degradation,
                        "minimum": java_baseline_mrr - max_degradation,
                    },
                ),
                _gate(
                    "current_pipeline_p95_latency",
                    _is_finite_number(current_p95_latency_ms)
                    and current_p95_latency_ms <= max_p95_latency_ms,
                    observed=current_p95_latency_ms,
                    threshold=max_p95_latency_ms,
                ),
                _gate(
                    "current_pipeline_fallback_rate",
                    _is_finite_number(current_fallback_rate)
                    and current_fallback_rate <= max_fallback_rate,
                    observed=current_fallback_rate,
                    threshold=max_fallback_rate,
                ),
                _gate(
                    "current_pipeline_error_rate",
                    _is_finite_number(current_error_rate)
                    and current_error_rate <= max_error_rate,
                    observed=current_error_rate,
                    threshold=max_error_rate,
                ),
                _gate(
                    "current_pipeline_judged_answers",
                    current_pipeline_judge_report is not None
                    and current_pipeline_judge_report.get("status") == "passed",
                    observed=(
                        current_pipeline_judge_report.get("status")
                        if current_pipeline_judge_report is not None
                        else current_pipeline_judge_error
                    ),
                    threshold="passed",
                ),
            ]
        )

    status_gates = gates
    release_gate_source = "all_gates"
    if current_pipeline:
        status_gates = [
            gate
            for gate in gates
            if gate["name"].startswith("current_pipeline_")
            or gate["name"] in {"canary_smoke", "chroma_vector_store_runtime"}
        ]
        release_gate_source = "current_pipeline_and_runtime_smoke"
    status = (
        "passed"
        if status_gates and all(gate["status"] != "failed" for gate in status_gates)
        else "failed"
    )
    return {
        "status": status,
        "version": "2.8",
        "release_gate_source": release_gate_source,
        "canary": {
            "skipped": smoke_skipped,
            "report": canary_report,
            "error": canary_error,
        },
        "current_pipeline": {
            "enabled": current_pipeline,
            "answer_policy": answer_policy,
            "report": current_pipeline_report,
            "error": current_pipeline_error,
            "judge_report": current_pipeline_judge_report,
            "judge_error": current_pipeline_judge_error,
            "java_baseline_required": java_baseline_required,
            "java_baseline_report": java_baseline_report,
            "java_baseline_error": java_baseline_report_error,
        },
        "ragas": {
            "rounds": [
                {"round": row["round"], "sha256": row["sha256"]}
                for row in ragas_reports
            ],
            "stable": stable,
            "report": first_report,
            "error": ragas_error,
        },
        "gates": gates,
    }


def _find_metric(
    report: dict[str, Any],
    run_id: str,
    mode: str,
) -> dict[str, Any] | None:
    for row in report["retrieval_metrics"]:
        if row["run_id"] == run_id and row["mode"] == mode:
            return row
    return None


def _gate(
    name: str,
    passed: bool,
    *,
    observed: Any | None = None,
    threshold: Any | None = None,
    skipped: bool = False,
) -> dict[str, Any]:
    gate = {
        "name": name,
        "status": "skipped" if skipped else ("passed" if passed else "failed"),
    }
    if observed is not None:
        gate["observed"] = observed
    if threshold is not None:
        gate["threshold"] = threshold
    return gate


def _is_finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_stable_metadata_scalar(value: Any) -> bool:
    return (
        isinstance(value, (str, bool, int))
        or isinstance(value, float)
        and math.isfinite(value)
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_java_baseline_provenance(report: dict[str, Any]) -> bool:
    generated_at = _parse_utc_timestamp(report.get("generated_at"))
    return (
        report.get("producer") == JAVA_BASELINE_PRODUCER
        and report.get("runtime_scope") == JAVA_BASELINE_RUNTIME_SCOPE
        and generated_at is not None
        and generated_at <= datetime.now(timezone.utc)
        and _is_sha256(report.get("source_attestation_sha256"))
    )


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_dataset_contract(dataset: Any) -> bool:
    return (
        isinstance(dataset, dict)
        and _is_positive_int(dataset.get("case_count"))
        and _is_sha256(dataset.get("case_ids_sha256"))
        and _is_sha256(dataset.get("cohort_sha256"))
        and dataset.get("cohort_fingerprint_version") == "pipeline-golden-v1"
    )


def _recomputed_retrieval_evidence(
    report: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        not isinstance(report, dict)
        or report.get("version") != PIPELINE_REPORT_VERSION
    ):
        return None
    dataset = report.get("dataset")
    top_k = report.get("top_k")
    cases = report.get("cases")
    if (
        not _valid_dataset_contract(dataset)
        or not _is_positive_int(top_k)
        or not isinstance(cases, list)
        or len(cases) != dataset["case_count"]
    ):
        return None

    case_ids: list[str] = []
    case_signatures: list[dict[str, Any]] = []
    recall_values: list[float] = []
    mrr_values: list[float] = []
    for case in cases:
        if not isinstance(case, dict):
            return None
        case_id = case.get("case_id")
        golden_case_sha256 = case.get("golden_case_sha256")
        truth_ids = case.get("ground_truth_context_ids")
        matched_ids = case.get("matched_ground_truth_context_ids")
        retrieved_results = case.get("retrieved_results")
        if (
            not isinstance(case_id, str)
            or not case_id.strip()
            or case_id in case_ids
            or not _is_sha256(golden_case_sha256)
            or not isinstance(truth_ids, list)
            or not truth_ids
            or not all(
                isinstance(context_id, str) and context_id
                for context_id in truth_ids
            )
            or len(set(truth_ids)) != len(truth_ids)
            or not isinstance(matched_ids, list)
            or not isinstance(retrieved_results, list)
            or len(matched_ids) != len(retrieved_results)
            or len(retrieved_results) > top_k
            or not all(
                context_id is None
                or (
                    isinstance(context_id, str)
                    and context_id in truth_ids
                )
                for context_id in matched_ids
            )
            or not all(
                isinstance(result, dict)
                and isinstance(result.get("chunk_id"), str)
                and bool(result["chunk_id"].strip())
                and isinstance(result.get("text"), str)
                and bool(result["text"].strip())
                and isinstance(result.get("metadata"), dict)
                and set(result["metadata"]).issubset(
                    MATCH_METADATA_FIELDS
                )
                and all(
                    _is_stable_metadata_scalar(value)
                    for value in result["metadata"].values()
                )
                for result in retrieved_results
            )
        ):
            return None
        evidence_ids = [result["chunk_id"] for result in retrieved_results]
        evidence_contexts = [result["text"] for result in retrieved_results]
        if (
            "retrieved_context_ids" in case
            and case.get("retrieved_context_ids") != evidence_ids
        ) or (
            "retrieved_contexts" in case
            and case.get("retrieved_contexts") != evidence_contexts
        ):
            return None
        case_ids.append(case_id)
        case_signatures.append(
            {
                "case_id": case_id,
                "golden_case_sha256": golden_case_sha256,
                "ground_truth_context_ids": truth_ids,
            }
        )
        first_match = matched_ids[0] if matched_ids else None
        recall_values.append(
            (1.0 / len(truth_ids)) if first_match in set(truth_ids) else 0.0
        )
        reciprocal_rank = 0.0
        for rank, context_id in enumerate(matched_ids, start=1):
            if context_id is not None:
                reciprocal_rank = 1.0 / rank
                break
        mrr_values.append(reciprocal_rank)

    expected_case_ids_sha256 = hashlib.sha256(
        json.dumps(
            case_ids,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if dataset.get("case_ids_sha256") != expected_case_ids_sha256:
        return None
    return {
        "case_signatures": case_signatures,
        "recall_at_1": round(sum(recall_values) / len(recall_values), 4),
        "mrr": round(sum(mrr_values) / len(mrr_values), 4),
    }


def _retrieval_summary_matches(
    declared: Any,
    recomputed: dict[str, Any],
) -> bool:
    if not isinstance(declared, dict):
        return False
    return all(
        _is_finite_number(declared.get(metric))
        and math.isclose(
            float(declared[metric]),
            float(recomputed[metric]),
            abs_tol=1e-9,
        )
        for metric in ("recall_at_1", "mrr")
    )


def _validate_acceptance_thresholds(**thresholds: float) -> None:
    unit_interval_names = {
        "min_mrr",
        "min_precision_at_1",
        "min_recall_at_1",
        "java_baseline_recall_at_1",
        "java_baseline_mrr",
        "max_degradation",
        "max_fallback_rate",
        "max_error_rate",
    }
    for name, value in thresholds.items():
        if not _is_finite_number(value):
            raise ValueError(f"{name} threshold must be a finite number")
        if name in unit_interval_names and not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} threshold must be between 0 and 1")
    if thresholds["max_p95_latency_ms"] <= 0.0:
        raise ValueError("max_p95_latency_ms threshold must be greater than 0")


def _report_sha256(report: dict[str, Any]) -> str:
    payload = json.dumps(
        report,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _serialize_report(report: dict[str, Any]) -> str:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def _reject_non_finite_json(value: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number is forbidden: {value}")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
