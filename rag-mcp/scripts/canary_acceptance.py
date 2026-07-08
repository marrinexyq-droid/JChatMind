from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.canary_smoke import run_canary
from src.evaluation.ragas_cases import as_report_dict, evaluate_dataset


DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "evaluation"


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
    require_chroma: bool = False,
) -> dict[str, Any]:
    if ragas_rounds < 1:
        raise ValueError("ragas_rounds must be at least 1")

    canary_report = None
    canary_error = None
    if run_smoke:
        try:
            canary_report = _run_smoke_canary(collection, require_chroma=require_chroma)
        except Exception as exc:
            canary_error = str(exc)
    ragas_reports = [
        _evaluate_ragas_round(dataset_dir, index + 1)
        for index in range(ragas_rounds)
    ]
    report = _build_report(
        canary_report=canary_report,
        canary_error=canary_error,
        smoke_skipped=not run_smoke,
        ragas_reports=ragas_reports,
        min_total_cases=min_total_cases,
        gate_run_id=gate_run_id,
        gate_mode=gate_mode,
        min_mrr=min_mrr,
        min_precision_at_1=min_precision_at_1,
        require_chroma=require_chroma,
    )

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
    parser.add_argument("--require-chroma", action="store_true")
    args = parser.parse_args(argv)

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
        require_chroma=args.require_chroma,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
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


def _build_report(
    *,
    canary_report: dict[str, Any] | None,
    canary_error: str | None,
    smoke_skipped: bool,
    ragas_reports: list[dict[str, Any]],
    min_total_cases: int,
    gate_run_id: str,
    gate_mode: str,
    min_mrr: float,
    min_precision_at_1: float,
    require_chroma: bool,
) -> dict[str, Any]:
    first_report = ragas_reports[0]["report"]
    hashes = [row["sha256"] for row in ragas_reports]
    stable = len(set(hashes)) == 1
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

    status = "passed" if all(gate["status"] != "failed" for gate in gates) else "failed"
    return {
        "status": status,
        "version": "2.2",
        "canary": {
            "skipped": smoke_skipped,
            "report": canary_report,
            "error": canary_error,
        },
        "ragas": {
            "rounds": [
                {"round": row["round"], "sha256": row["sha256"]}
                for row in ragas_reports
            ],
            "stable": stable,
            "report": first_report,
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


def _report_sha256(report: dict[str, Any]) -> str:
    payload = json.dumps(
        report,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
