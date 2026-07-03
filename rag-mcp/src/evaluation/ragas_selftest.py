from __future__ import annotations

import importlib.util


def check_ragas_available() -> dict[str, str | bool]:
    spec = importlib.util.find_spec("ragas")
    if spec is None:
        return {
            "available": False,
            "message": "ragas is not installed in this Python environment",
        }
    return {
        "available": True,
        "message": "ragas is importable",
    }
