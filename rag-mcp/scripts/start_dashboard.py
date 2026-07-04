from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.service import DashboardService


def main() -> int:
    parser = argparse.ArgumentParser(description="Start or validate the rag-mcp dashboard.")
    parser.add_argument(
        "--settings",
        type=Path,
        default=PROJECT_ROOT / "config" / "settings.yaml",
        help="Path to a rag-mcp settings.yaml file.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate dashboard inputs without starting Streamlit.",
    )
    args = parser.parse_args()

    if args.check:
        overview = DashboardService(args.settings).overview()
        print("rag-mcp dashboard check")
        print(f"settings={args.settings}")
        print(f"collections={overview.collection_count}")
        print(f"documents={overview.document_count}")
        print(f"chunks={overview.chunk_count}")
        print(f"traces={overview.trace_count}")
        print(f"latest_evaluation_report={overview.latest_evaluation_report or ''}")
        return 0

    try:
        from streamlit.web import cli as streamlit_cli
    except ModuleNotFoundError:
        print(
            "Streamlit is not installed. Install the dashboard extra first: "
            "pip install -e .[dashboard]",
            file=sys.stderr,
        )
        return 1

    app_path = PROJECT_ROOT / "src" / "dashboard" / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--",
        "--settings",
        str(args.settings),
    ]
    streamlit_cli.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
