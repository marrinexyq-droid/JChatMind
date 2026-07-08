# RAG DEV_SPEC Replacement 2.4 Implementation Plan

Goal: codify the remaining production cutover gap as an executable readiness
report.

Version: `2.4`

Scope:

- Add `scripts/rag_cutover_readiness.py`.
- Check the original replacement success criteria against the current repo.
- Mark production blockers separately from warnings.
- Return a non-zero exit code when the repo is not ready for default cutover,
  unless `--allow-not-ready` is passed.
- Emit a machine-readable JSON report for local planning.
- Add tests using synthetic repo layouts so the checks are stable.
- Document the readiness command.

Out of scope:

- Enabling Python RAG in the default Spring profile.
- Deleting Java RAG internals.
- Adding Chroma or LLM-judged RAGAS in this slice.
- Pushing the branch.

Acceptance:

1. The readiness report says the current repo is not production-cutover-ready.
2. The report names the concrete blockers and next actions.
3. A synthetic ready repo passes the same checks.
4. Tests and local script execution pass.
