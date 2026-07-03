from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.settings import Settings
from src.evaluation.runner import summarize_environment


def main() -> int:
    settings = Settings.load(Path("config/settings.yaml"))
    summary = summarize_environment(Path(settings.evaluation.baseline_report))
    print("RAG-MCP evaluation environment")
    print(f"baseline_report_exists={summary.baseline_report_exists}")
    print(f"baseline_report_path={summary.baseline_report_path}")
    print(f"ragas_available={summary.ragas_available}")
    print(f"ragas_message={summary.ragas_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
