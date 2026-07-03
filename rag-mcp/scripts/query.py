from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.query_engine import QueryEngine
from src.core.settings import Settings
from src.core.types import SearchRequest
from src.libs.embeddings import HashEmbeddingProvider
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Query the local rag-mcp index.")
    parser.add_argument("query")
    parser.add_argument("--collection", default="default")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=["vector", "hybrid", "hybrid-rerank"], default="hybrid")
    args = parser.parse_args()

    settings = Settings.load(PROJECT_ROOT / "config/settings.yaml")
    engine = QueryEngine(
        vector_store=SqliteVectorStore(PROJECT_ROOT / settings.storage.vector_store_db),
        sparse_index=SqliteSparseIndex(PROJECT_ROOT / settings.storage.bm25_path),
        embedding_provider=HashEmbeddingProvider(),
        trace_writer=JsonlTraceWriter(PROJECT_ROOT / settings.storage.traces_path),
        rrf_k=settings.retrieval.rrf_k,
    )
    response = engine.search(
        SearchRequest(
            query=args.query,
            collection=args.collection,
            top_k=args.top_k,
            mode=args.mode,
        )
    )
    print(response.answer_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
