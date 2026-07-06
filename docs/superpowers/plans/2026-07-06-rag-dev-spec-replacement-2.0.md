# RAG DEV_SPEC Replacement 2.0 Implementation Plan

Goal: add an executable canary harness that proves the Python RAG/MCP path is
ready before using the Java `rag-canary` profile for real traffic.

Version: `2.0`

Scope:

- Add `rag-mcp/scripts/canary_smoke.py`.
- Run the canary in an isolated temporary project root by default so it does not
  mutate local `rag-mcp/data` or `rag-mcp/logs`.
- Validate the full Python path:
  - create canary settings and document
  - ingest document
  - check MCP `initialize`
  - check MCP `tools/list`
  - check MCP `get_system_status`
  - query `query_knowledge_hub`
  - fetch `get_document_summary`
  - verify ingestion and query traces were written
- Emit a machine-readable JSON report for future Java/Spring canary workflows.
- Add integration tests for the importable `run_canary()` function and CLI
  execution.
- Document the canary flow in `rag-mcp/README.md`.

Out of scope:

- Starting the full Spring Boot application.
- Pushing the branch.
- Enabling Python RAG in the default profile.
- Running real model providers or external rerankers.

Acceptance:

1. The canary passes without network or external services.
2. The canary does not write to the repository data/log directories by default.
3. The report includes readiness, query, summary, and trace evidence.
4. Python tests, Java bridge tests, RAGAS offline evaluation, and code review
   pass.
