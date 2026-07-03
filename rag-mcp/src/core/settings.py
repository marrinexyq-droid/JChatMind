from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class StorageSettings(BaseModel):
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


class RetrievalSettings(BaseModel):
    rrf_k: int = 60
    default_top_k: int = 5
    candidate_pool_size: int = 20
    rerank_backend: str = "none"


class EvaluationSettings(BaseModel):
    baseline_report: str
    metrics_dir: str


class Settings(BaseModel):
    app_name: str
    storage: StorageSettings
    embedding: EmbeddingSettings
    retrieval: RetrievalSettings
    evaluation: EvaluationSettings

    @classmethod
    def load(cls, path: Path) -> "Settings":
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.model_validate(raw)
