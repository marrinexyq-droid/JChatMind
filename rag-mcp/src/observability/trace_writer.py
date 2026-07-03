from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonlTraceWriter:
    def __init__(self, path: Path):
        self.path = path

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
