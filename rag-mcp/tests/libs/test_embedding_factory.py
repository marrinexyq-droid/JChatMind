import io
import json
import urllib.error

import pytest

from src.core.settings import EmbeddingSettings
from src.libs.embedding_factory import build_embedding_provider
from src.libs.embeddings import HashEmbeddingProvider
from src.libs.ollama_embeddings import OllamaEmbeddingProvider
from src.mcp_server import server as server_module


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.payload


def test_factory_uses_ollama_settings():
    settings = EmbeddingSettings(
        provider="ollama",
        model="bge-m3",
        base_url="http://localhost:11434",
    )

    provider = build_embedding_provider(settings)

    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.model == "bge-m3"
    assert provider.base_url == "http://localhost:11434"


def test_factory_uses_hash_only_when_explicitly_configured():
    settings = EmbeddingSettings(provider="hash", model="hash", base_url="")

    provider = build_embedding_provider(settings)

    assert isinstance(provider, HashEmbeddingProvider)


def test_hash_provider_fingerprint_tracks_the_configured_model():
    legacy = build_embedding_provider(
        EmbeddingSettings(provider="hash", model="legacy-hash", base_url="")
    )
    replacement = build_embedding_provider(
        EmbeddingSettings(provider="hash", model="replacement-hash", base_url="")
    )

    assert legacy.compatibility_fingerprint() != replacement.compatibility_fingerprint()


def test_ollama_provider_fingerprint_tracks_the_configured_model():
    legacy = OllamaEmbeddingProvider("http://ollama.local:11434", "bge-m3")
    replacement = OllamaEmbeddingProvider("http://ollama.local:11434", "nomic-embed-text")

    assert legacy.compatibility_fingerprint() != replacement.compatibility_fingerprint()


def test_factory_rejects_unsupported_provider():
    settings = EmbeddingSettings(provider="unknown", model="test", base_url="")

    with pytest.raises(ValueError, match="unsupported embedding provider: unknown"):
        build_embedding_provider(settings)


def test_ollama_provider_posts_configured_model_and_text(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(b'{"embeddings": [[0.25, -0.5]]}')

    monkeypatch.setattr("src.libs.ollama_embeddings.urllib.request.urlopen", fake_urlopen)
    provider = OllamaEmbeddingProvider("http://ollama.local:11434/", "bge-m3")

    vector = provider.embed_text("Embedding settings control runtime")

    assert vector == [0.25, -0.5]
    assert captured == {
        "url": "http://ollama.local:11434/api/embed",
        "method": "POST",
        "body": {"model": "bge-m3", "input": "Embedding settings control runtime"},
        "timeout": 30.0,
    }


def test_ollama_provider_reports_non_success_response(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "model unavailable"}'),
        )

    monkeypatch.setattr("src.libs.ollama_embeddings.urllib.request.urlopen", fake_urlopen)
    provider = OllamaEmbeddingProvider("http://ollama.local:11434", "bge-m3")

    with pytest.raises(RuntimeError, match="ollama embedding request failed with HTTP 503"):
        provider.embed_text("test")


def test_ollama_provider_reports_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "src.libs.ollama_embeddings.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(b"not-json"),
    )
    provider = OllamaEmbeddingProvider("http://ollama.local:11434", "bge-m3")

    with pytest.raises(RuntimeError, match="ollama embedding response was not valid JSON"):
        provider.embed_text("test")


def test_ollama_provider_reports_empty_vector(monkeypatch):
    monkeypatch.setattr(
        "src.libs.ollama_embeddings.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(b'{"embeddings": [[]]}'),
    )
    provider = OllamaEmbeddingProvider("http://ollama.local:11434", "bge-m3")

    with pytest.raises(RuntimeError, match="ollama embedding response did not contain a non-empty vector"):
        provider.embed_text("test")


def test_build_local_hub_uses_embedding_settings(monkeypatch, tmp_path):
    settings = server_module.Settings.model_validate(
        {
            "app_name": "test-rag-mcp",
            "storage": {
                "vector_store_backend": "sqlite",
                "chroma_path": "data/db/chroma",
                "bm25_path": "data/db/bm25",
                "ingestion_history_db": "data/db/ingestion_history.db",
                "image_index_db": "data/db/image_index.db",
                "traces_path": "logs/traces.jsonl",
            },
            "embedding": {
                "provider": "ollama",
                "model": "bge-m3",
                "base_url": "http://ollama.local:11434",
            },
            "retrieval": {},
            "evaluation": {"baseline_report": "output/report.md", "metrics_dir": "output/metrics"},
        }
    )
    observed = []

    def fake_build_provider(embedding_settings):
        observed.append(embedding_settings)
        return HashEmbeddingProvider()

    monkeypatch.setattr(
        server_module.Settings,
        "load",
        classmethod(lambda _cls, _path: settings),
    )
    monkeypatch.setattr(
        server_module,
        "build_embedding_provider",
        fake_build_provider,
        raising=False,
    )

    server_module.build_local_hub(tmp_path)

    assert observed == [settings.embedding]
