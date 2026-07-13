from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.settings import Settings
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embedding_factory import build_embedding_provider
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import build_vector_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete a document from the rag-mcp index.")
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
    result = pipeline.delete(args.source, collection=args.collection)
    print(f"status={result.status}")
    print(f"source_path={result.source_path}")
    print(f"collection={result.collection}")
    print(f"vector_chunks_deleted={result.vector_chunks_deleted}")
    print(f"sparse_chunks_deleted={result.sparse_chunks_deleted}")
    print(f"history_deleted={result.history_deleted}")
    print(f"message={result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
