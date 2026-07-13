from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request
from typing import Any

from src.core.settings import LlmSettings


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class OllamaLLMProvider(BaseLLMProvider):
    base_url: str
    model: str
    timeout_seconds: float = 30.0

    def generate(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("OLLAMA_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/api/generate",
            data=json.dumps(
                {"model": self.model, "prompt": prompt, "stream": False}
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"ollama generation request failed with HTTP {exc.code}"
            ) from exc
        except (OSError, TimeoutError) as exc:
            raise RuntimeError("ollama generation request failed") from exc

        if not 200 <= status < 300:
            raise RuntimeError(f"ollama generation request failed with HTTP {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("ollama generation response was not valid JSON") from exc
        return _response_text(payload)


def build_llm_provider(settings: LlmSettings) -> BaseLLMProvider:
    if settings.provider == "ollama":
        return OllamaLLMProvider(
            base_url=settings.base_url,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
        )
    raise ValueError(f"unsupported LLM provider: {settings.provider}")


def _response_text(payload: Any) -> str:
    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, str) or not response.strip():
        raise RuntimeError("ollama generation response did not contain an answer")
    return response.strip()
