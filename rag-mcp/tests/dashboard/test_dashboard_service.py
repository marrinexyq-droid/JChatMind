import json
import subprocess
import sys
from pathlib import Path

from src.core.types import ChunkRecord
from src.dashboard.service import DashboardService
from src.libs.embeddings import HashEmbeddingProvider
from src.storage.vector_store import SqliteVectorStore


def test_dashboard_service_summarizes_index_traces_and_evaluation(tmp_path):
    settings_path = write_settings(tmp_path)
    seed_vector_store(tmp_path)
    write_traces(tmp_path)
    write_evaluation_report(tmp_path)

    service = DashboardService(settings_path)

    overview = service.overview()
    assert overview.collection_count == 1
    assert overview.document_count == 2
    assert overview.chunk_count == 3
    assert overview.trace_count == 2
    assert overview.ingestion_trace_count == 1
    assert overview.query_trace_count == 1
    assert overview.malformed_trace_rows == 1
    assert overview.latest_evaluation_report == "ragas_cases_offline_report.json"
    assert overview.total_evaluation_cases == 1014

    collections = service.list_collections()
    assert collections[0].name == "battle"
    assert collections[0].chunk_count == 3

    documents = service.list_documents(collection="battle")
    assert [document.document_id for document in documents] == ["doc-1", "doc-2"]
    assert documents[0].source_path == "docs/doc-1.md"

    chunks = service.list_chunks(collection="battle", limit=2)
    assert len(chunks) == 2
    assert chunks[0].chunk_id == "c1"
    assert "hybrid retrieval" in chunks[0].text_preview

    traces = service.list_traces(trace_type="query")
    assert len(traces) == 1
    assert traces[0].trace_id == "t-query"
    assert traces[0].stages[0]["name"] == "fusion"

    report = service.latest_evaluation_report()
    assert report is not None
    assert report.split_counts["gold_retrieval"] == 58
    assert report.retrieval_metric_count == 1


def test_dashboard_check_script_does_not_require_streamlit(tmp_path):
    settings_path = write_settings(tmp_path)
    seed_vector_store(tmp_path)

    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "rag-mcp" / "scripts" / "start_dashboard.py"),
            "--settings",
            str(settings_path),
            "--check",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "rag-mcp dashboard check" in result.stdout
    assert "collections=1" in result.stdout


def write_settings(project_root: Path) -> Path:
    config_dir = project_root / "config"
    config_dir.mkdir()
    settings_path = config_dir / "settings.yaml"
    settings_path.write_text(
        """
app_name: rag-mcp-test

storage:
  chroma_path: data/db/chroma
  vector_store_db: data/db/vector_store.db
  bm25_path: data/db/bm25
  ingestion_history_db: data/db/ingestion_history.db
  image_index_db: data/db/image_index.db
  traces_path: logs/traces.jsonl

embedding:
  provider: test
  model: hash
  base_url: http://localhost

retrieval:
  rrf_k: 60
  default_top_k: 5
  candidate_pool_size: 20
  rerank_backend: none

evaluation:
  baseline_report: output/baseline.md
  metrics_dir: output/metrics
""".lstrip(),
        encoding="utf-8",
    )
    return settings_path


def seed_vector_store(project_root: Path) -> None:
    provider = HashEmbeddingProvider(dimensions=16)
    store = SqliteVectorStore(project_root / "data" / "db" / "vector_store.db")
    chunks = [
        ChunkRecord(
            id="c1",
            document_id="doc-1",
            collection="battle",
            text="hybrid retrieval uses dense and sparse evidence",
            metadata={"source_path": "docs/doc-1.md", "title": "Doc One"},
        ),
        ChunkRecord(
            id="c2",
            document_id="doc-1",
            collection="battle",
            text="rerank improves comparison questions",
            metadata={"source_path": "docs/doc-1.md", "title": "Doc One"},
        ),
        ChunkRecord(
            id="c3",
            document_id="doc-2",
            collection="battle",
            text="query traces expose retrieval stages",
            metadata={"source_path": "docs/doc-2.md", "title": "Doc Two"},
        ),
    ]
    store.upsert_chunks(chunks, [provider.embed_text(chunk.text) for chunk in chunks])


def write_traces(project_root: Path) -> None:
    traces_path = project_root / "logs" / "traces.jsonl"
    traces_path.parent.mkdir()
    rows = [
        {"trace_id": "t-ingest", "trace_type": "ingestion", "stages": []},
        {"trace_id": "t-query", "trace_type": "query", "stages": [{"name": "fusion"}]},
    ]
    traces_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\nnot-json\n",
        encoding="utf-8",
    )


def write_evaluation_report(project_root: Path) -> None:
    metrics_dir = project_root / "output" / "metrics"
    metrics_dir.mkdir(parents=True)
    (metrics_dir / "ragas_cases_offline_report.json").write_text(
        json.dumps(
            {
                "inventory": {
                    "total_cases": 1014,
                    "split_counts": {"gold_retrieval": 58},
                },
                "retrieval_metrics": [{"run_id": "baseline", "mode": "hybrid"}],
            }
        ),
        encoding="utf-8",
    )
