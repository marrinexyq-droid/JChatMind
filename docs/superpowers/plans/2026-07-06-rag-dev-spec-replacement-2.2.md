# RAG DEV_SPEC Replacement 2.2 Implementation Plan

Goal: add a repeatable canary acceptance entrypoint that combines the Python
smoke canary with multi-round offline RAGAS stability checks.

Version: `2.2`

Scope:

- Add `rag-mcp/scripts/canary_acceptance.py`.
- Run the isolated canary smoke harness by default.
- Run offline RAGAS case evaluation for a configurable number of rounds.
- Hash each RAGAS round to prove deterministic stability.
- Gate on minimum case inventory and target retrieval quality.
- Emit a machine-readable JSON report for local or CI use.
- Document the acceptance command in `rag-mcp/README.md`.
- Add tests for the acceptance report, threshold failure, and CLI output.

Out of scope:

- Launching the Spring Boot application from Python.
- Pushing the branch.
- Changing Java `rag-canary` profile defaults.
- Replacing the standalone `canary_smoke.py` or `evaluate_ragas_cases.py`
  entrypoints.

Acceptance:

1. A single command can run canary smoke plus multi-round RAGAS evaluation.
2. The report records RAGAS round hashes and marks stability.
3. Failing inventory or retrieval thresholds returns a failed report.
4. Fast test mode can skip smoke while still validating RAGAS gates.
5. Python tests, RAGAS multi-round evaluation, and local review pass.
