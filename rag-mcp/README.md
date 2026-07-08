# rag-mcp

Version 1.0 of the Python RAG replacement subsystem for JChatMind.

This project starts as a measured replacement spine. It owns Python-side
contracts, trace logging, and evaluation harnesses before becoming the canonical
ingestion and query implementation.

Run tests:

```bash
python -m pytest -q
```

Run evaluation environment check:

```bash
python scripts/evaluate.py
```

Build the strict RAGAS battle dataset:

```bash
python scripts/build_ragas_cases.py
```

Run offline dataset evaluation:

```bash
python scripts/evaluate_ragas_cases.py --output-json output/metrics/ragas_cases_offline_report.json
```

The offline evaluator computes retrieval metrics from the strict JSONL dataset.
LLM-judged RAGAS metrics such as faithfulness and answer relevancy run through
the judged gate:

```bash
python scripts/evaluate_ragas_judged.py --mock-judge --limit 5 --output-json output/metrics/ragas_judged_report.json
```

`--mock-judge` is deterministic and is intended for harness stability checks.
For a real judge-model gate, set `RAGAS_JUDGE_PROVIDER`, `RAGAS_JUDGE_MODEL`,
and `RAGAS_JUDGE_API_KEY`; Google/Gemini can also use `GOOGLE_API_KEY` with the
default `gemini-2.5-flash` model. Secrets are read only from environment
variables. Use `--answer-policy generated` once evaluated answers are written
into `ragas_cases.combined.jsonl`; the default `reference` policy is a wiring
smoke test for the judge harness.

Ingest a Markdown document:

```bash
python scripts/ingest.py path/to/document.md --collection default
```

Query the local index:

```bash
python scripts/query.py "What does this document say about RAG?" --collection default
```

Run the MCP-compatible stdio server:

```bash
python main.py
```

The server exposes `query_knowledge_hub`, `list_collections`,
`get_system_status`, and `get_document_summary` over JSON-RPC stdio. It keeps
protocol responses on stdout so MCP clients can consume them.

Version 1.0 is complete when tests pass and the evaluation script reports whether
the existing Java RAG baseline report and the optional `ragas` package are
available in the local environment.

Version 1.1 adds an offline ingestion/query MVP using deterministic local
embeddings, SQLite vector storage, SQLite sparse search, and hybrid fusion.

Version 1.2 adds a minimal MCP-compatible stdio tool layer over the local
ingestion/query MVP.

Version 1.3 adds a guarded Java bridge that can call the MCP stdio tool layer
behind `rag.python-bridge.enabled`, with the legacy Java RAG path as fallback.

Version 1.4 adds a local management dashboard layer for browsing indexed
collections, chunks, ingestion/query traces, and the latest offline evaluation
JSON report.

Version 1.5 adds a Python-side reranker seam for `hybrid-rerank`. The default
configuration keeps `rerank_backend: none`, preserving local offline behavior.
Set `rerank_backend: noop` for traced pass-through reranking, or
`rerank_backend: http` to call the existing FastAPI reranker-compatible
`/rerank` service, controlled by `reranker_base_url` and
`reranker_timeout_seconds` in `config/settings.yaml`. Query traces record rerank
success and fallback details.

Version 1.6 adds a guarded Java ingestion bridge. When
`rag.python-bridge.ingestion-enabled=true`, Java document uploads invoke
`rag-mcp/scripts/ingest.py <file> --collection <kbId>` so the Python index can be
kept warm before query cutover. The bridge remains disabled and fail-open by
default.

Version 1.7 adds guarded delete synchronization. Python exposes
`scripts/delete_document.py <file> --collection <kbId>` and Java document
deletion calls it when `rag.python-bridge.ingestion-enabled=true`, removing
matching vector chunks, sparse chunks, and ingestion history before local
document deletion continues.

Version 1.8 adds a guarded bridge readiness layer. Python exposes
`get_system_status` for MCP status checks, and Java can verify `initialize`,
`tools/list`, and status payloads through the same stdio bridge before query
cutover. Spring Actuator health reports the bridge as disabled without spawning
Python when both bridge flags are off.

Version 1.9 adds a development canary cutover profile. Start the Java app with
`--spring.profiles.active=rag-canary` to enable Python query and ingestion bridge
flags with legacy fallback and MCP readiness gating. The default profile remains
fully disabled.

Version 2.0 adds an isolated canary smoke harness:

```bash
python scripts/canary_smoke.py
```

The canary creates a temporary `rag-mcp` project root, ingests a sample document,
checks MCP readiness, queries `query_knowledge_hub`, verifies document summary
and traces, prints a JSON report, and removes the temporary data by default.

Version 2.1 wires the canary into Java's `rag-canary` profile. When
`rag.python-bridge.canary-preflight-enabled=true`, JChatMind runs
`scripts/canary_smoke.py` before accepting canary traffic and fails fast when
`canary-preflight-fail-on-error=true`.

Version 2.2 adds a combined acceptance gate:

```bash
python scripts/canary_acceptance.py --ragas-rounds 3 --output-json output/metrics/canary_acceptance_report.json
```

The acceptance gate runs the isolated canary smoke harness, repeats the offline
RAGAS battle evaluation, records SHA-256 hashes for each round, and fails when
the case inventory or target retrieval metrics drop below the configured
thresholds. Use `--skip-smoke` for fast metric-only checks.

Version 2.3 exposes the same flow at the repository root for local and CI use:

```bash
python scripts/verify_rag_canary.py --acceptance-rounds 3
```

The root verifier runs Python tests, the canary acceptance gate, and Java bridge
tests, then returns a JSON report with per-step status.

Version 2.4 adds a production cutover readiness report:

```bash
python ../scripts/rag_cutover_readiness.py --allow-not-ready
```

The report compares the current repository against the original replacement
success criteria and lists blockers before Python RAG can become the default
canonical implementation.

Version 2.5 adds a configurable judge-model RAGAS gate:

```bash
python scripts/evaluate_ragas_judged.py --mock-judge --limit 5
```

The gate reports faithfulness and answer relevancy over answer-generation cases.
Remote judging is configured through environment variables only, with
`GOOGLE_API_KEY` supported for the Gemini default.

Validate dashboard inputs without Streamlit:

```bash
python scripts/start_dashboard.py --check
```

Start the optional Streamlit dashboard:

```bash
pip install -e .[dashboard]
python scripts/start_dashboard.py
```
