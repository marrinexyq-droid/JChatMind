# RAG DEV_SPEC Replacement 1.6 Implementation Plan

Goal: add a guarded Java-to-Python ingestion bridge so documents uploaded through
JChatMind can be dual-written into the Python `rag-mcp` index before query
cutover.

Version: `1.6`

Scope:

- Extend `rag.python-bridge` with ingestion-specific settings.
- Add a Java `PythonRagIngestionClient` that invokes `rag-mcp/scripts/ingest.py`
  with the uploaded file path and knowledge-base collection.
- Call the ingestion bridge from `DocumentFacadeServiceImpl` after file storage
  and document metadata persistence.
- Keep ingestion bridge disabled by default and fail-open by default.
- Add unit tests for command construction, disabled behavior, fail-open/fail-closed
  behavior, and upload-path wiring.

Out of scope:

- Removing old Java chunk generation.
- Making Python query bridge enabled by default.
- Persistent Python worker process.
- Python-side delete synchronization.

Acceptance:

1. Existing upload behavior is unchanged while `ingestion-enabled=false`.
2. When enabled, Java can invoke Python ingestion with `--collection <kbId>`.
3. Python ingestion failure does not break upload unless `fail-on-ingestion-error`
   is true.
4. Targeted Java tests, Python tests, RAGAS offline evaluation, and code review
   pass.
