# RAG DEV_SPEC Replacement 1.4 Implementation Plan

Goal: add the first local management dashboard layer for `rag-mcp` so ingestion,
query traces, indexed data, and evaluation reports are inspectable outside the
Java chat UI.

Version: `1.4`

Scope:

- Pure Python dashboard service functions for:
  - overview metrics
  - collection and chunk browsing
  - ingestion and query trace browsing
  - latest offline evaluation report loading
- Optional Streamlit app shell with the six DEV_SPEC dashboard pages:
  - Overview
  - Data Browser
  - Ingestion Manager
  - Ingestion Traces
  - Query Traces
  - Evaluation Panel
- CLI entrypoint `scripts/start_dashboard.py`.
- Tests that do not require Streamlit to be installed.

Out of scope:

- Mutating ingestion state from the dashboard.
- Running Streamlit in CI.
- Replacing the React product UI.
- Adding authentication.

Acceptance:

1. Dashboard service can read local SQLite vector chunks and summarize
   collections.
2. Dashboard service can read `logs/traces.jsonl`, tolerate malformed rows, and
   filter ingestion/query traces.
3. Dashboard service can load the latest JSON evaluation report from
   `output/metrics`.
4. `scripts/start_dashboard.py --check` validates configuration without starting
   Streamlit.
5. Python tests pass and the existing Java bridge path remains unchanged.
