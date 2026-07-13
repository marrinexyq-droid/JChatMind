import os
import subprocess
import sys
from pathlib import Path

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


def _write_explicit_hash_runtime_settings(runtime_root: Path, model: str = "hash") -> None:
    config_path = runtime_root / "config" / "settings.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
app_name: test-rag-mcp

storage:
  vector_store_backend: sqlite
  chroma_path: data/db/chroma
  vector_store_db: data/db/vector_store.db
  bm25_path: data/db/bm25
  ingestion_history_db: data/db/ingestion_history.db
  image_index_db: data/db/image_index.db
  traces_path: logs/traces.jsonl

embedding:
  provider: hash
  model: %s
  base_url: ""

retrieval: {}

evaluation:
  baseline_report: output/report.md
  metrics_dir: output/metrics
""".lstrip() % model,
        encoding="utf-8",
    )


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


def test_cli_scripts_start_in_subprocess_with_explicit_hash_runtime_root(tmp_path):
    runtime_root = tmp_path / "runtime-root"
    source = tmp_path / "cli-subprocess.md"
    collection = "cli-subprocess"
    source.write_text("# CLI subprocess\n\nHybrid retrieval stays offline.", encoding="utf-8")
    _write_explicit_hash_runtime_settings(runtime_root)
    project_root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "RAG_MCP_RUNTIME_ROOT": str(runtime_root)}

    def run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, f"scripts/{script}", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    ingested = run("ingest.py", str(source), "--collection", collection)
    queried = run("query.py", "hybrid retrieval", "--collection", collection)
    deleted = run("delete_document.py", str(source), "--collection", collection)

    assert ingested.returncode == 0, ingested.stderr
    assert "status=ingested" in ingested.stdout
    assert queried.returncode == 0, queried.stderr
    assert "Evidence found:" in queried.stdout
    assert deleted.returncode == 0, deleted.stderr
    assert "status=deleted" in deleted.stdout


def test_query_cli_reports_reindex_required_after_embedding_configuration_changes(tmp_path):
    runtime_root = tmp_path / "runtime-root"
    source = tmp_path / "cli-subprocess.md"
    collection = "cli-subprocess"
    source.write_text("# CLI subprocess\n\nEmbedding compatibility is enforced.", encoding="utf-8")
    _write_explicit_hash_runtime_settings(runtime_root, model="legacy-hash")
    project_root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "RAG_MCP_RUNTIME_ROOT": str(runtime_root)}

    ingested = subprocess.run(
        [sys.executable, "scripts/ingest.py", str(source), "--collection", collection],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    _write_explicit_hash_runtime_settings(runtime_root, model="replacement-hash")
    queried = subprocess.run(
        [sys.executable, "scripts/query.py", "compatibility", "--collection", collection],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert ingested.returncode == 0, ingested.stderr
    assert queried.returncode != 0
    assert "re-index required" in queried.stderr
