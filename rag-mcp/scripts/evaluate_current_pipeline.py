from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from src.core.types import RetrievalMode
from src.evaluation.pipeline_runner import (
    PipelineEvaluationRunner,
    as_report_dict,
    load_pipeline_cases,
)
from src.mcp_server.server import build_local_hub


DEFAULT_DATASET_DIR = SCRIPT_ROOT / "data" / "evaluation"


def run_current_pipeline(
    *,
    project_root: Path,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    collection: str,
    top_k: int = 5,
    mode: RetrievalMode = "hybrid",
    limit: int | None = None,
) -> dict[str, Any]:
    hub = build_local_hub(project_root.resolve())
    runner = PipelineEvaluationRunner(hub.query_engine, top_k=top_k, mode=mode)
    cases = load_pipeline_cases(dataset_dir.resolve(), limit=limit)
    return as_report_dict(runner.run(cases, collection))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Run answer-generation cases through the current rag-mcp pipeline."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(os.environ.get("RAG_MCP_RUNTIME_ROOT", SCRIPT_ROOT)),
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--collection", default="rag-canary")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--mode",
        choices=["vector", "hybrid", "hybrid-rerank"],
        default="hybrid",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    report = run_current_pipeline(
        project_root=args.project_root,
        dataset_dir=args.dataset_dir,
        collection=args.collection,
        top_k=args.top_k,
        mode=args.mode,
        limit=args.limit,
    )
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
