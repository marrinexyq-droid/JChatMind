from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from src.libs.embeddings import BaseEmbeddingProvider


@dataclass(frozen=True)
class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    base_url: str
    model: str
    timeout_seconds: float = 30.0

    def embed_text(self, text: str) -> list[float]:
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/api/embed",
            data=json.dumps({"model": self.model, "input": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"ollama embedding request failed with HTTP {exc.code}"
            ) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError(f"ollama embedding request failed: {exc}") from exc

        if not 200 <= status < 300:
            raise RuntimeError(f"ollama embedding request failed with HTTP {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("ollama embedding response was not valid JSON") from exc

        return _first_embedding(payload)


def _first_embedding(payload: Any) -> list[float]:
    embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(embeddings, list) or not embeddings:
        raise RuntimeError("ollama embedding response did not contain a non-empty vector")
    vector = embeddings[0]
    if not isinstance(vector, list) or not vector:
        raise RuntimeError("ollama embedding response did not contain a non-empty vector")
    if not all(isinstance(value, int | float) and not isinstance(value, bool) for value in vector):
        raise RuntimeError("ollama embedding response contained a non-numeric vector")
    return [float(value) for value in vector]
