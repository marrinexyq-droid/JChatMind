from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.ragas_cases import as_report_dict, evaluate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the strict RAGAS battle dataset offline."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "evaluation",
        help="Directory containing ragas_cases.combined.jsonl.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path for a JSON report.",
    )
    args = parser.parse_args()

    evaluation = evaluate_dataset(args.dataset_dir)
    report = as_report_dict(evaluation)

    print("RAGAS battle dataset offline evaluation")
    print(f"total_cases={report['inventory']['total_cases']}")
    for split, count in report["inventory"]["split_counts"].items():
        print(f"split.{split}={count}")

    print("retrieval_metrics:")
    for row in report["retrieval_metrics"]:
        print(
            "  "
            f"{row['run_id']}/{row['mode']} "
            f"n={row['sample_count']} "
            f"recall@1={row['recall_at_1']:.4f} "
            f"recall@5={row['recall_at_5']:.4f} "
            f"mrr={row['mrr']:.4f} "
            f"ndcg@5={row['ndcg_at_5']:.4f}"
        )

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"output_json={args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
