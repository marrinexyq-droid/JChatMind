from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class TraceContext:
    trace_type: str
    inputs: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    stages: list[dict[str, Any]] = field(default_factory=list)

    def record_stage(
        self,
        name: str,
        method: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
        elapsed_ms: float | None = None,
    ) -> None:
        self.stages.append(
            {
                "name": name,
                "method": method,
                "provider": provider,
                "details": details or {},
                "elapsed_ms": elapsed_ms,
            }
        )

    def finish(self, error: str | None = None) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "trace_type": self.trace_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": self.inputs,
            "stages": self.stages,
            "error": error,
        }
