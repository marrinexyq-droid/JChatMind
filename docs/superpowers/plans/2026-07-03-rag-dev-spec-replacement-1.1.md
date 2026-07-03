# RAG DEV_SPEC Replacement 1.1 Implementation Plan

Goal: turn the `rag-mcp` 1.0 spine into a runnable local ingestion and retrieval MVP.

Version: `1.1`

Scope:

- Markdown/text ingestion.
- SHA256-based incremental skip.
- Deterministic local embedding provider for offline tests.
- SQLite vector store with cosine search.
- SQLite sparse index using FTS5 BM25 when available, with token-overlap fallback.
- Hybrid query through `QueryEngine`.
- CLI scripts for ingest and query.
- No Java RAG behavior changes.
- No mandatory external model or Chroma dependency in this slice.

Acceptance:

1. A sample Markdown file can be ingested into a named collection.
2. Re-ingesting the unchanged file returns a skipped result.
3. Chunks are persisted with deterministic IDs and metadata.
4. QueryEngine can return cited evidence from local stores.
5. `python scripts/ingest.py ...` and `python scripts/query.py ...` run locally.
6. Full test suite passes for three consecutive rounds.

Out of scope for 1.1:

- PDF parsing.
- Chroma adapter.
- Ollama/OpenAI embedding calls.
- MCP server.
- Streamlit dashboard.
- Java bridge.

Implementation tasks:

1. Add ingestion loader, splitter, integrity store, and pipeline result types.
2. Add deterministic embedding provider, SQLite vector store, SQLite sparse index, and RRF fusion.
3. Upgrade `QueryEngine` from no-evidence stub to optional store-backed retrieval.
4. Add `scripts/ingest.py` and `scripts/query.py`.
5. Add integration tests covering ingest, skip, and query.
6. Run 3-round stability verification and code review.
