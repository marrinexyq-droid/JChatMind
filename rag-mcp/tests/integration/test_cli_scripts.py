import sys

from scripts import delete_document, ingest, query
from src.core.settings import EmbeddingSettings, Settings
from src.libs.embeddings import HashEmbeddingProvider


def _offline_settings() -> Settings:
    return Settings.model_validate(
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
            "embedding": {"provider": "hash", "model": "hash", "base_url": ""},
            "retrieval": {},
            "evaluation": {"baseline_report": "output/report.md", "metrics_dir": "output/metrics"},
        }
    )


def _configure_scripts(monkeypatch, tmp_path, settings: Settings) -> None:
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, _path: settings))
    for module in (ingest, query, delete_document):
        monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)


def test_cli_scripts_run_offline_end_to_end_with_explicit_hash_settings(
    monkeypatch, capsys, tmp_path
):
    source = tmp_path / "cli.md"
    collection = f"cli-test-{tmp_path.name}"
    source.write_text("# CLI RAG\n\nThe command line path supports hybrid retrieval.", encoding="utf-8")
    _configure_scripts(monkeypatch, tmp_path, _offline_settings())

    monkeypatch.setattr(sys, "argv", ["ingest.py", str(source), "--collection", collection])
    assert ingest.main() == 0
    assert "status=ingested" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["query.py", "hybrid retrieval", "--collection", collection])
    assert query.main() == 0
    assert "Evidence found:" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["delete_document.py", str(source), "--collection", collection])
    assert delete_document.main() == 0
    assert "status=deleted" in capsys.readouterr().out


def test_cli_scripts_build_provider_from_configured_settings(monkeypatch, tmp_path):
    source = tmp_path / "cli.md"
    collection = f"cli-test-{tmp_path.name}"
    source.write_text("# CLI RAG\n\nThe command line path supports hybrid retrieval.", encoding="utf-8")
    settings = _offline_settings()
    observed: list[EmbeddingSettings] = []

    def fake_build_provider(embedding_settings: EmbeddingSettings) -> HashEmbeddingProvider:
        observed.append(embedding_settings)
        return HashEmbeddingProvider()

    _configure_scripts(monkeypatch, tmp_path, settings)
    for module in (ingest, query, delete_document):
        monkeypatch.setattr(module, "build_embedding_provider", fake_build_provider, raising=False)

    monkeypatch.setattr(sys, "argv", ["ingest.py", str(source), "--collection", collection])
    assert ingest.main() == 0
    monkeypatch.setattr(sys, "argv", ["query.py", "hybrid retrieval", "--collection", collection])
    assert query.main() == 0
    monkeypatch.setattr(sys, "argv", ["delete_document.py", str(source), "--collection", collection])
    assert delete_document.main() == 0

    assert observed == [settings.embedding, settings.embedding, settings.embedding]
