from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp_server.server import JsonRpcMcpServer, build_local_hub, serve_stdio


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    server = JsonRpcMcpServer(build_local_hub(PROJECT_ROOT))
    return serve_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())
