# RAG DEV_SPEC Replacement 1.2 Implementation Plan

Goal: make the local `rag-mcp` MVP callable through a minimal MCP-compatible
stdio surface and remove confirmed generated-file redundancy.

Version: `1.2`

Scope:

- MCP JSON-RPC stdio dispatcher.
- Tools: `query_knowledge_hub`, `list_collections`, `get_document_summary`.
- Local factory that reuses the existing SQLite stores and deterministic
  embedding provider for offline repeatability.
- Storage helpers for collection and document inspection.
- Tracked generated Python bytecode cleanup.

Out of scope:

- Java bridge.
- External embedding/rerank provider calls.
- Streamlit dashboard.
- Deleting legacy `rag_eval/output`, because it remains the baseline source for
  RAGAS dataset generation and regression comparison.

Acceptance:

1. `python main.py` can answer JSON-RPC `tools/list` over stdio.
2. MCP tool calls return text content and structured payloads.
3. Existing ingestion/query CLI behavior remains unchanged.
4. Full Python test suite passes for three consecutive rounds.
5. RAGAS offline dataset evaluator still reports the strict battle dataset.
