# RAG DEV_SPEC Replacement 1.7 Implementation Plan

Goal: add guarded delete synchronization so Java document deletion can remove
matching chunks from the Python `rag-mcp` index before query cutover.

Version: `1.7`

Scope:

- Add Python index deletion by `collection + source_path`.
- Add `rag-mcp/scripts/delete_document.py` for local and Java bridge use.
- Extend `PythonRagIngestionClient` with a delete command that uses the same
  guarded bridge settings.
- Wire `DocumentFacadeServiceImpl.deleteDocument` to call Python delete before
  local file/database deletion when index sync is enabled.
- Add Python and Java tests for delete behavior, disabled behavior, and CLI
  wiring.

Out of scope:

- Removing Java chunk/graph deletion.
- Enabling Python bridge by default.
- Deleting by Java document id inside Python storage.
- Persistent Python worker process.

Acceptance:

1. Python delete removes vector chunks, sparse chunks, and ingestion history for
   the same `collection + source_path`.
2. Java deletion does not resolve Python paths or call Python when the bridge is
   disabled.
3. Java deletion calls Python delete before local file deletion when enabled.
4. Targeted Java tests, Python tests, RAGAS offline evaluation, and code review
   pass.
