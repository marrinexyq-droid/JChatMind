# RAG DEV_SPEC Replacement 2.3 Implementation Plan

Goal: expose the RAG canary acceptance flow as a project-level command and wire
it into GitHub Actions.

Version: `2.3`

Scope:

- Add a root `scripts/verify_rag_canary.py` orchestration script.
- Run Python tests, the 2.2 canary acceptance gate, and Java bridge tests from
  one command.
- Emit a machine-readable verification report with step status and output tails.
- Add a GitHub Actions workflow that runs the same command.
- Document the local command and CI behavior.
- Add unit tests for command construction, skip flags, and failure reporting.

Out of scope:

- Pushing the branch.
- Changing Java `rag-canary` profile defaults.
- Replacing Maven or pytest with a new build system.
- Uploading or committing generated acceptance reports.

Acceptance:

1. Local users can run one command from the repository root.
2. CI invokes the same project-level command.
3. The report marks skipped, passed, and failed steps explicitly.
4. Script tests pass without launching Maven or long-running canary commands.
5. Full local verification passes with four acceptance rounds.
