# RAG DEV_SPEC Replacement 2.6 Implementation Plan

Goal: make Chroma the canonical Python dense vector store while preserving
offline test stability.

Version: `2.6`

Scope:

- Add a `VectorStore` protocol and `ChromaVectorStore` adapter.
- Add `build_vector_store()` so CLI, MCP, canary, and dashboard share one
  backend decision.
- Set the default storage backend to `chroma`.
- Keep SQLite as a legacy fallback when `chromadb` is unavailable locally.
- Add `rag-mcp[chroma]` optional dependency metadata.
- Stop dashboard reads from depending directly on the SQLite `chunks` table.
- Scope dense-store physical ids by collection so identical chunk ids in
  different collections do not overwrite each other.
- Add `--require-chroma` to canary smoke and acceptance gates for production
  runtime verification.
- Strengthen the cutover readiness Chroma check so it verifies dependency,
  adapter, factory, settings model, default config, and strict runtime gates.
- Add fake-Chroma tests for the adapter contract and factory fallback.

Out of scope:

- Installing `chromadb` in the current environment.
- Migrating existing SQLite vector rows into a Chroma collection.
- Enabling Python RAG in the default Spring profile.
- Deprecating or deleting Java RAG internals.
- Pushing the branch.

Acceptance:

1. Chroma readiness blocker is removed from the current repository report.
2. Offline tests do not require a real `chromadb` install.
3. CLI/MCP/canary/dashboard all construct vector storage through the same
   factory.
4. SQLite remains available only as legacy fallback/test storage.
5. Production canary can be run with `--require-chroma`.
6. Targeted and full Python regression tests pass.
