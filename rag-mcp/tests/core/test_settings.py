from pathlib import Path

from src.core.settings import Settings


def test_loads_default_settings_file():
    settings = Settings.load(Path("config/settings.yaml"))

    assert settings.app_name == "rag-mcp"
    assert settings.storage.chroma_path == "data/db/chroma"
    assert settings.evaluation.baseline_report.endswith("rag_eval_report.md")
