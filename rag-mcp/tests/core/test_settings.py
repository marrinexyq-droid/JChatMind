from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.settings import Settings


def test_loads_default_settings_file():
    settings = Settings.load(Path("config/settings.yaml"))

    assert settings.app_name == "rag-mcp"
    assert settings.storage.vector_store_backend == "chroma"
    assert settings.storage.sqlite_fallback_when_chroma_unavailable is True
    assert settings.storage.chroma_path == "data/db/chroma"
    assert settings.llm is not None
    assert settings.llm.provider == "ollama"
    assert settings.llm.model == "llama3.2"
    assert settings.llm.timeout_seconds == 30.0
    assert settings.evaluation.baseline_report.endswith("rag_eval_report.md")


def test_rejects_missing_storage_section(tmp_path):
    config = tmp_path / "settings.yaml"
    config.write_text("app_name: rag-mcp\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        Settings.load(config)
