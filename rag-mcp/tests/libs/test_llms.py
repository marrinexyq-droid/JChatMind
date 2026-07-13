import json
import urllib.error

import pytest
from src.core.settings import LlmSettings
from src.libs.llms import OllamaLLMProvider, build_llm_provider


def test_llm_factory_uses_ollama_settings():
    settings = LlmSettings(
        provider="ollama",
        model="llama3.2",
        base_url="http://ollama.local:11434",
        timeout_seconds=12.0,
    )

    provider = build_llm_provider(settings)

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.model == "llama3.2"
    assert provider.base_url == "http://ollama.local:11434"
    assert provider.timeout_seconds == 12.0


class FakeResponse:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.payload


def test_ollama_llm_posts_configured_model_and_reads_key_from_environment(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse(b'{"response": "RRF combines lists [C1]."}')

    monkeypatch.setenv("OLLAMA_API_KEY", "test-only-key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaLLMProvider("http://ollama.local:11434/", "llama3.2", 12.0)

    answer = provider.generate("Use only evidence.")

    assert answer == "RRF combines lists [C1]."
    assert captured == {
        "url": "http://ollama.local:11434/api/generate",
        "method": "POST",
        "body": {"model": "llama3.2", "prompt": "Use only evidence.", "stream": False},
        "authorization": "Bearer test-only-key",
        "timeout": 12.0,
    }


def test_ollama_llm_generation_errors_do_not_leak_environment_key(monkeypatch):
    credential = "test-only-key"

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError(f"connection rejected for Bearer {credential}")

    monkeypatch.setenv("OLLAMA_API_KEY", credential)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaLLMProvider("http://ollama.local:11434", "llama3.2")

    with pytest.raises(RuntimeError, match="^ollama generation request failed$") as exc_info:
        provider.generate("Use only evidence.")

    assert credential not in str(exc_info.value)


def test_ollama_llm_reports_only_http_status_for_http_errors(monkeypatch):
    credential = "test-only-key"

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            503,
            f"Bearer {credential}",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setenv("OLLAMA_API_KEY", credential)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaLLMProvider("http://ollama.local:11434", "llama3.2")

    with pytest.raises(
        RuntimeError, match="^ollama generation request failed with HTTP 503$"
    ) as exc_info:
        provider.generate("Use only evidence.")

    assert credential not in str(exc_info.value)


def test_ollama_llm_rejects_missing_generated_answer(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout: FakeResponse(b'{"model": "llama3.2"}')
    )
    provider = OllamaLLMProvider("http://ollama.local:11434", "llama3.2")

    with pytest.raises(
        RuntimeError, match="^ollama generation response did not contain an answer$"
    ):
        provider.generate("Use only evidence.")
