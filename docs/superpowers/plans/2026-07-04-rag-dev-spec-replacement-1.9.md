# RAG DEV_SPEC Replacement 1.9 Implementation Plan

Goal: add a development canary cutover path for the Java query bridge, guarded
by MCP readiness so chat requests do not become the first bridge probe.

Version: `1.9`

Scope:

- Add a configurable Java readiness gate for `PythonBridgeRagService`.
- Cache readiness results for a short TTL to avoid spawning Python for every
  query while still detecting bridge changes during canary testing.
- Add a `rag-canary` Spring profile that enables Python query/ingestion bridge
  with fallback and readiness gate enabled.
- Keep the default profile unchanged: Python query and ingestion bridges remain
  disabled.
- Add unit tests for disabled gate behavior, ready gate behavior, not-ready
  fallback behavior, fail-closed behavior, and TTL caching.

Out of scope:

- Enabling Python query bridge in the default profile.
- Removing legacy Java RAG fallback.
- Running a persistent Python MCP worker.
- Replacing React trace rendering.

Acceptance:

1. When `readiness-gate-enabled=false`, existing bridge behavior is unchanged.
2. When the gate is enabled and MCP readiness is ready, Java queries can use the
   Python result.
3. When the gate is enabled and MCP readiness is unavailable or not ready,
   fallback behavior follows `fallback-on-error`.
4. Readiness checks are cached for `readiness-cache-ttl-ms`.
5. Targeted Java tests, Python tests, RAGAS offline evaluation, and code review
   pass.
