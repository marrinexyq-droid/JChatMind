# RAG DEV_SPEC Replacement 2.5 Implementation Plan

Goal: add a configurable judge-model RAGAS gate for answer-generation quality.

Version: `2.5`

Scope:

- Add `rag-mcp/src/evaluation/ragas_judged.py`.
- Add `rag-mcp/scripts/evaluate_ragas_judged.py`.
- Evaluate answer-generation cases with faithfulness and answer relevancy
  thresholds.
- Keep local verification deterministic through `--mock-judge`.
- Read judge credentials only from environment variables.
- Support Google/Gemini judge configuration through `GOOGLE_API_KEY` or the
  explicit `RAGAS_JUDGE_*` variables.
- Update docs so the cutover readiness report can verify the judged RAGAS gate.
- Add tests for case loading, env configuration, parsing, fake judge scoring,
  and the CLI.

Out of scope:

- Committing any API key.
- Enabling Python RAG as the default Spring profile.
- Replacing SQLite vector storage with Chroma.
- Deleting Java RAG internals.
- Pushing the branch.

Acceptance:

1. `python scripts/evaluate_ragas_judged.py --mock-judge --limit 5` passes.
2. The script reports faithfulness and answer relevancy metrics.
3. Missing judge credentials produce a `not_configured` report without leaking
   secrets.
4. The cutover readiness report no longer blocks on
   `llm_judged_ragas_gate_configured`.
5. Targeted and full Python tests pass.
