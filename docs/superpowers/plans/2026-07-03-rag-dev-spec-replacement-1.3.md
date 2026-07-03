# RAG DEV_SPEC Replacement 1.3 Implementation Plan

Goal: introduce a guarded Java-to-Python RAG bridge without removing the current
Java RAG implementation.

Version: `1.3`

Scope:

- Java `RagService` decorator that is `@Primary` and delegates to legacy Java RAG
  by default.
- `rag.python-bridge` configuration block, default disabled.
- Java MCP stdio client that invokes `rag-mcp/main.py` through
  `query_knowledge_hub`.
- Python MCP citation payload gains `text` so Java can reconstruct
  `ScoredChunk` evidence.
- Unit tests for parser, bridge routing, and fallback behavior.

Out of scope:

- Deleting `RagServiceImpl`.
- Replacing Java ingestion.
- Running Python as a persistent daemon.
- GitHub repository split.

Acceptance:

1. Existing Java behavior is unchanged while `rag.python-bridge.enabled=false`.
2. When enabled, Java can accept Python MCP search results as `RagSearchResult`.
3. Python failure or empty evidence falls back to legacy Java RAG by default.
4. Java tests and Python tests pass.
