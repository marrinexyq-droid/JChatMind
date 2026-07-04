# RAG DEV_SPEC Replacement 1.5 Implementation Plan

Goal: make `hybrid-rerank` a real Python `rag-mcp` query mode instead of only a
Java-side behavior.

Version: `1.5`

Scope:

- Add a Python reranker seam under `rag-mcp/src/libs`.
- Add a no-op reranker and an HTTP adapter for the existing local FastAPI
  reranker service at `/rerank`.
- Extend `QueryEngine` to retrieve a candidate pool, rerank it for
  `hybrid-rerank`, and fall back to fused ordering on reranker errors.
- Wire reranker settings into CLI and MCP local hub construction.
- Add unit tests for reranker ordering, fallback, and HTTP response parsing.

Out of scope:

- Loading sentence-transformers in-process.
- Changing the existing Java `RerankServiceImpl`.
- Starting the reranker sidecar automatically.
- Making rerank the default query mode.

Acceptance:

1. `hybrid-rerank` retrieves at least `candidate_pool_size` candidates before
   final top-k selection.
2. Configured HTTP reranker can reorder candidates and emits `source="rerank"`.
3. Reranker failure records a trace fallback and returns fused candidates.
4. Default `rerank_backend: none` preserves current behavior.
5. Python tests, RAGAS offline evaluation, and Java bridge tests pass.
