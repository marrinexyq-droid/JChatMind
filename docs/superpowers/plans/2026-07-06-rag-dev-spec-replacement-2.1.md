# RAG DEV_SPEC Replacement 2.1 Implementation Plan

Goal: connect the Python canary smoke harness to the Java `rag-canary` profile
so the profile can run an automatic preflight before accepting canary traffic.

Version: `2.1`

Scope:

- Add Java-side canary preflight settings under `rag.python-bridge`.
- Add a Spring `ApplicationRunner` that invokes
  `rag-mcp/scripts/canary_smoke.py` when preflight is enabled.
- Parse the JSON canary report and fail if `status != passed`.
- Keep preflight disabled in the default profile.
- Enable fail-fast preflight in `application-rag-canary.yaml`.
- Add unit tests for disabled behavior, command construction, JSON parsing,
  fail-open process failure, fail-closed process failure, and YAML values.

Out of scope:

- Starting Spring Boot from the Python canary.
- Pushing the branch.
- Removing legacy Java fallback.
- Making `rag-canary` the default profile.

Acceptance:

1. Default profile never starts Python for canary preflight.
2. `rag-canary` profile enables preflight and fail-fast behavior.
3. Preflight command uses the configured Python executable, args, project root,
   and collection.
4. Preflight parses the 2.0 canary JSON report.
5. Targeted Java tests, Python tests, RAGAS offline evaluation, and code review
   pass.
