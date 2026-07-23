# rag-mcp

Version 1.0 of the Python RAG replacement subsystem for JChatMind.

This project starts as a measured replacement spine. It owns Python-side
contracts, trace logging, and evaluation harnesses before becoming the canonical
ingestion and query implementation.

Run tests:

Python 3.11 is required for the locked all-extras environment. Select it
explicitly on a new checkout, especially on Windows where Python 3.12 would
require local MSVC build tools for `chroma-hnswlib`:

```powershell
uv sync --python 3.11 --frozen --all-extras --group dev
uv run pytest -q
```

Install the canonical Chroma vector backend when you want to run without the
local SQLite fallback:

```bash
pip install -e .[chroma]
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

Ingest a Markdown or text-based PDF document:

```bash
python scripts/ingest.py path/to/document.md --collection default
python scripts/ingest.py path/to/manual.pdf --collection default
```

PDF ingestion preserves page metadata through splitting. Image-only or scanned
PDFs need OCR before they can produce retrievable evidence.

Query the local index:

```bash
python scripts/query.py "What does this document say about RAG?" --collection default
```

When the optional `llm` section is configured, the query path uses the selected
Ollama model to generate an evidence-grounded answer. Every published claim must
use a citation marker present in the retrieved evidence, such as `[C1]`. A model
timeout, invalid citation, missing citation, or provider error falls back to the
stable evidence-only answer and records `fallback: true` in the query trace.

```yaml
llm:
  provider: ollama
  model: llama3.2
  base_url: http://localhost:11434
  timeout_seconds: 30
```

## Embedding runtime configuration

The default `config/settings.yaml` uses Ollama with the `bge-m3` model. Before
running the normal ingest, query, MCP, or dashboard paths, make sure Ollama is
reachable at `embedding.base_url` and that the configured model is available:

```bash
ollama pull bge-m3
ollama serve
```

For deterministic offline work, set the embedding configuration explicitly to
Hash rather than relying on the production default:

```yaml
embedding:
  provider: hash
  model: hash
  base_url: ""
```

The canary already creates an isolated temporary runtime root with those Hash
settings, so it remains offline:

```bash
python scripts/canary_smoke.py
```

CLI scripts normally use the checked-in `rag-mcp` root. To keep an offline or
test runtime separate, point them at a root containing its own
`config/settings.yaml` with `RAG_MCP_RUNTIME_ROOT` while still running the
scripts from this repository root:

```powershell
$env:RAG_MCP_RUNTIME_ROOT = "C:\temp\rag-mcp-runtime"
python scripts/ingest.py C:\docs\note.md --collection notes
python scripts/query.py "note" --collection notes
```

Ingestion history persists an embedding compatibility fingerprint for the local
index. An unchanged file is skipped only when its provider configuration is
also compatible. Because the Chroma backend uses one physical vector index for
this runtime, changing embedding provider or model never silently replaces or
mixes vectors: ingest, CLI query, and MCP query instead return a clear
`re-index required` error while any collection still has the old fingerprint.

To switch embedding configuration safely, explicitly delete every indexed
document in every local collection with the existing `delete_document.py`
command, then ingest all sources again using the new configuration. The data is
not automatically deleted on a configuration mismatch. Once the local index is
empty, the Chroma collection is safely recreated on its next ingest or query so
the new vector dimension can be established without a Chroma dimension error.

Run the MCP-compatible stdio server:

```bash
python main.py
```

The server exposes `query_knowledge_hub`, `list_collections`,
`get_system_status`, and `get_document_summary` over JSON-RPC stdio. It keeps
protocol responses on stdout so MCP clients can consume them.

## Convergence status

The convergence implementation has completed the code for Tasks 1–8A and the
Task 9A cutover-gate hardening: workspace
cleanup, repository secret gates, a frozen Python 3.11/uv environment, runtime
embedding selection, fail-closed index integrity, Markdown/PDF ingestion, and
citation-constrained answer generation, followed by current-pipeline evaluation
and strict generated-answer gates, cross-runtime trace propagation, and a clean
frontend baseline. The latest complete Python run recorded 340 passing tests.
Task 9A adds three fixed independent live burn-in rounds, same-cohort
Java-baseline gates, indexed Chroma preflight, fail-closed Canary routing,
single-writer ingestion after Python succeeds, and compensating cleanup when
fail-closed ingestion aborts. A real strict evaluation still requires a reproducibly indexed
Golden collection, Ollama embedding and LLM models, Chroma, and configured Judge
credentials; missing runtime dependencies produce a failed report instead of a
reference-answer, unjudged-answer, or SQLite release pass. The current local
strict run stops at the empty `acceptance-canary` index; the matching 182-case
Java baseline artifact is also absent. Default cutover, Java-to-MCP end-to-end
SLO evidence, hybrid-rerank live parity, Java retirement, dashboard actions, and
MCP resources remain pending. The default Python Bridge is intentionally still
disabled.

Version 1.0 is complete when tests pass and the evaluation script reports whether
the existing Java RAG baseline report and the optional `ragas` package are
available in the local environment.

Version 1.1 added the original offline ingestion/query MVP using deterministic
local embeddings, SQLite vector storage, SQLite sparse search, and hybrid
fusion. SQLite vector storage is now a legacy fallback.

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
flags and MCP readiness gating. Task 9A makes this Canary Profile fail closed on
readiness, query, and ingestion errors; the default profile remains fully
disabled until strict cutover evidence passes.

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

Version 2.6 makes Chroma the canonical dense vector store:

```yaml
storage:
  vector_store_backend: chroma
  sqlite_fallback_when_chroma_unavailable: true
  chroma_path: data/db/chroma
```

CLI, MCP, canary, and dashboard construction now go through one vector store
factory. In local environments without `chromadb`, the default config falls back
to the legacy SQLite vector store so offline tests and canary smoke checks still
run. Production installs should include `rag-mcp[chroma]` and run the strict
runtime gate:

```bash
python scripts/canary_smoke.py --require-chroma
python scripts/canary_acceptance.py --require-chroma --ragas-rounds 3
```

Version 2.7 runs answer-generation cases through the current QueryEngine and
writes results separately from the static observation baseline:

```bash
python scripts/evaluate_current_pipeline.py \
  --collection rag-canary \
  --output-json output/metrics/current_pipeline.json
```

Current-pipeline report schema v1.1 records each ranked result's chunk ID, text,
and only the stable metadata needed for matching (`golden_context_id`,
`context_id`, `source_path`, `title`, and `heading`), together with its mapped
Golden context ID, answer provenance, latency, and errors. Runtime chunk IDs are
resolved by direct ID, explicit context metadata, source path/heading, or
reference-context text before the report aggregates live Recall@1, MRR, P95
latency, fallback rate, and error rate.
`SearchResponse.answer_source` distinguishes `generated_answer`,
`evidence_fallback`, and `no_evidence`. Judge-RAGAS generated mode must read the
current report and refuses missing cases, errors, blank answers, or fallback
answers:

```bash
python scripts/evaluate_ragas_judged.py \
  --answer-policy generated \
  --pipeline-report output/metrics/current_pipeline.json \
  --mock-judge
```

The strict acceptance path is:

```bash
python scripts/canary_acceptance.py \
  --require-chroma \
  --current-pipeline \
  --answer-policy generated \
  --java-baseline-report data/evaluation/java_current_pipeline_baseline.json \
  --ragas-rounds 3
```

This gate fails when Golden schema validation fails, no cases ran, any case
errored, an answer is blank, an answer used reference/evidence fallback, live
Recall@1/MRR misses threshold, the configured Judge rejects any generated
answer, Runtime Smoke fails, or the live vector backend is SQLite. Static RAGAS
observations remain available for harness regression, but their thresholds and
errors do not decide the current-pipeline release status.

Version 2.8 adds current-pipeline comparison and runtime gates. Strict mode only
accepts a v1.1 Java baseline whose semantic cohort fingerprint, retrieval mode,
`top_k`, evaluator contract, and recomputed per-case metrics exactly match the
Python report and local Golden data. Readiness recomputes match/rank from the
ordered raw result evidence instead of trusting declared matched IDs. The older
58-case baseline cannot be compared with the 182-case answer-generation cohort.
Judge schema 2.5 evidence is recomputed from every score and bound to the exact
generated answer and retrieved contexts. Recall@1 and MRR may degrade by at most 0.02,
Python QueryEngine P95 latency must be at most 8000 ms, and fallback/error rates
must each be at most 0.01. The current-pipeline preflight also rejects an empty
persistent collection before spending time on answer-generation cases. These
runtime metrics use scope `python_query_engine`; Java-to-MCP/Agent/SSE
end-to-end SLO evidence is still required before default cutover.

Verifier/readiness version 3.0 separates ordinary CI wiring checks from actual
cutover evidence. From the repository root, run the strict operator gate without
skip flags:

```powershell
.\rag-mcp\.venv\Scripts\python.exe scripts\verify_rag_canary.py --strict-cutover --acceptance-rounds 3
.\rag-mcp\.venv\Scripts\python.exe scripts\rag_cutover_readiness.py --allow-not-ready
```

The strict verifier expects the same-cohort Java comparison artifact at
`rag-mcp/data/evaluation/java_current_pipeline_baseline.json`. Do not copy the
older 58-case metrics into that file; generate it from the exact case IDs and
retrieval mode used by the live Python report. Task 9A validates the artifact's
producer label (`jchatmind-java-current-pipeline-evaluator`), runtime scope
(`java_rag_retrieval`), timestamp, ordered raw result evidence, and current
`source_attestation_sha256`, but it does not mint Java runtime evidence. The fixed
`scripts/generate_java_rag_baseline.py` producer and an exact verifier execution
step are Task 9B deliverables and are currently absent, so readiness reports
`java_baseline_producer_present` as blocked. Until those pieces land, a hand-written
baseline is not release evidence even when its JSON fields are internally consistent.

Strict mode executes exactly three complete acceptance runs and writes each
round to a unique report. Readiness accepts only fresh v3.0 evidence whose round
artifacts exist and match the embedded reports, whose Python and fixed full Java
test commands passed exactly once, and whose Chroma, generated-answer, real
Judge, same-cohort baseline, quality and runtime evidence is internally
consistent. The non-strict command used by hosted CI remains a
harness/wiring check because hosted runners do not own the production corpus,
Ollama models, or Judge credentials.

Validate dashboard inputs without Streamlit:

```bash
python scripts/start_dashboard.py --check
```

Start the optional Streamlit dashboard:

```bash
pip install -e .[dashboard]
python scripts/start_dashboard.py
```
