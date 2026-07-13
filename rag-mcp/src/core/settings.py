from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class StorageSettings(BaseModel):
    vector_store_backend: str = "chroma"
    sqlite_fallback_when_chroma_unavailable: bool = True
    chroma_path: str
    vector_store_db: str = "data/db/vector_store.db"
    bm25_path: str
    ingestion_history_db: str
    image_index_db: str
    traces_path: str


class EmbeddingSettings(BaseModel):
    provider: str
    model: str
    base_url: str


class LlmSettings(BaseModel):
    provider: str = "ollama"
    model: str
    base_url: str
    timeout_seconds: float = 30.0


class RetrievalSettings(BaseModel):
    rrf_k: int = 60
    default_top_k: int = 5
    candidate_pool_size: int = 20
    rerank_backend: str = "none"
    reranker_base_url: str = "http://127.0.0.1:8001"
    reranker_timeout_seconds: float = 8.0


class EvaluationSettings(BaseModel):
    baseline_report: str
    metrics_dir: str


class Settings(BaseModel):
    app_name: str
    storage: StorageSettings
    embedding: EmbeddingSettings
    llm: LlmSettings | None = None
    retrieval: RetrievalSettings
    evaluation: EvaluationSettings

    @classmethod
    def load(cls, path: Path) -> "Settings":
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.model_validate(raw)
