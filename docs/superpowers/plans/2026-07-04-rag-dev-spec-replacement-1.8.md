# RAG DEV_SPEC Replacement 1.8 Implementation Plan

Goal: add a guarded query-bridge readiness layer so Java can verify the Python
`rag-mcp` MCP server before enabling query cutover.

Version: `1.8`

Scope:

- Add a Python MCP `get_system_status` tool that reports server readiness,
  collections, and indexed chunk counts without running a search query.
- Extend the Java `PythonRagMcpClient` with a readiness check that performs
  MCP `initialize`, `tools/list`, and `get_system_status` in one stdio session.
- Add a Spring Actuator `HealthIndicator` for the Python RAG bridge. It remains
  `UP` and marked disabled when both query and ingestion bridges are disabled,
  and checks MCP readiness only when either bridge is enabled.
- Keep `rag.python-bridge.enabled=false` and
  `rag.python-bridge.ingestion-enabled=false` as defaults.
- Add Python and Java tests for status payloads, readiness parsing, process
  fallback, and health indicator behavior.

Out of scope:

- Enabling Python query bridge by default.
- Removing legacy Java RAG fallback.
- Replacing the Java chat UI trace model.
- Starting a persistent Python MCP worker.

Acceptance:

1. `get_system_status` returns ready status, collection names, per-collection
   chunk counts, and total chunk count.
2. Java readiness succeeds only when required MCP tools are present and status
   payload is parseable.
3. Actuator health does not spawn Python while the bridge is fully disabled.
4. Targeted Java tests, Python tests, RAGAS offline evaluation, and code review
   pass.
