from __future__ import annotations

from src.core.settings import EmbeddingSettings
from src.libs.embeddings import BaseEmbeddingProvider, HashEmbeddingProvider
from src.libs.ollama_embeddings import OllamaEmbeddingProvider


def build_embedding_provider(settings: EmbeddingSettings) -> BaseEmbeddingProvider:
    if settings.provider == "ollama":
        return OllamaEmbeddingProvider(settings.base_url, settings.model)
    if settings.provider == "hash":
        return HashEmbeddingProvider()
    raise ValueError(f"unsupported embedding provider: {settings.provider}")
