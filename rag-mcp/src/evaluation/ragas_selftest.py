from __future__ import annotations

import importlib


def check_ragas_available() -> dict[str, str | bool]:
    try:
        importlib.import_module("ragas")
    except Exception as exc:
        return {
            "available": False,
            "message": f"ragas is not importable: {exc}",
        }
    return {
        "available": True,
        "message": "ragas is importable",
    }
