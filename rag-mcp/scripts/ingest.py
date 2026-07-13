from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("RAG_MCP_RUNTIME_ROOT", SCRIPT_ROOT)).resolve()
sys.path.insert(0, str(SCRIPT_ROOT))

from src.core.settings import Settings
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embedding_factory import build_embedding_provider
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import build_vector_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a Markdown/text document into rag-mcp.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--collection", default="default")
    args = parser.parse_args()

    settings = Settings.load(PROJECT_ROOT / "config/settings.yaml")
    pipeline = IngestionPipeline(
        history_db=PROJECT_ROOT / settings.storage.ingestion_history_db,
        vector_store=build_vector_store(PROJECT_ROOT, settings.storage),
        sparse_index=SqliteSparseIndex(PROJECT_ROOT / settings.storage.bm25_path),
        embedding_provider=build_embedding_provider(settings.embedding),
        trace_writer=JsonlTraceWriter(PROJECT_ROOT / settings.storage.traces_path),
    )
    result = pipeline.run(args.source, collection=args.collection)
    print(f"status={result.status}")
    print(f"document_id={result.document_id}")
    print(f"chunk_count={result.chunk_count}")
    print(f"collection={result.collection}")
    print(f"message={result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
