# Task 4 Report: embedding settings control runtime

## Status

DONE

## Commit

`b89c7c1ad2515557478e4942a46c38171b48c4f3` — `feat: connect embedding settings to runtime`

## RED / GREEN

- RED 1: `uv run pytest tests/libs/test_embedding_factory.py -q` failed during collection with `ModuleNotFoundError: No module named 'src.libs.embedding_factory'`.
- GREEN 1: after the minimal factory and Ollama adapter, the same suite passed: `7 passed`.
- RED 2: runtime-wiring tests failed exactly because `build_local_hub`, Canary, and `ingest.py`/`query.py`/`delete_document.py` did not call the factory (`3 failed, 10 passed`).
- GREEN 2: after the five entry points called `build_embedding_provider(settings.embedding)`, those tests passed: `13 passed`.

## Implementation

- Added `OllamaEmbeddingProvider`, which posts `{model, input}` to `<base_url>/api/embed` and raises clear `RuntimeError`s for HTTP failures, invalid JSON, empty vectors, and non-numeric vectors.
- Added `build_embedding_provider(EmbeddingSettings)` with explicit `ollama` and `hash` providers and unsupported-provider rejection.
- Replaced the direct Hash construction in `build_local_hub`, `ingest.py`, `query.py`, and `delete_document.py`.
- Updated Canary to consume its generated `provider: hash` settings through the same factory, preserving offline determinism.

## Test Coverage

- `tests/libs/test_embedding_factory.py`: factory selection; model/base URL request construction; HTTP, JSON, and empty-vector errors; server settings wiring.
- `tests/integration/test_canary_smoke.py`: Canary's explicit `provider: hash` settings reach the factory.
- `tests/integration/test_cli_scripts.py`: one offline end-to-end flow calls the real `ingest.py`/`query.py`/`delete_document.py` `main()` functions with explicit temporary hash settings and asserts ingestion, evidence retrieval, and deletion. A separate test verifies that all three entry points pass the configured settings to the factory.
- The prior subprocess test implicitly relied on hard-coded Hash despite the production default being Ollama. It was replaced with the explicit temporary hash configuration above so the same CLI flow remains deterministic without weakening the data-flow assertions or requiring a local Ollama server in CI.
- Focused plan command: `16 passed in 5.23s`.
- Full suite: `86 passed in 12.33s`.
- `git diff --check`: passed.

## Self-review

- Production `HashEmbeddingProvider(...)` references now exist only in its definition and the factory's explicit `provider == "hash"` branch.
- Default `config/settings.yaml` remains `ollama` / `bge-m3` / `http://localhost:11434`; no default runtime fallback silently selects Hash.
- No keys, cleanup code, lock files, frontend files, or `progress.md` were changed.

## Concerns

- Non-blocking: real default ingestion/query now requires a reachable configured Ollama service, as intended. Offline tests use explicit hash settings rather than relying on the production default.

## Post-review remediation

### Findings

- Ingestion history previously treated `(source_path, collection, content SHA-256)` as sufficient identity. A provider/model change therefore skipped an unchanged source and could leave incompatible dense vectors behind.
- Chroma keeps a dimension on its single physical local collection even after its records are deleted. Replacing only one source could therefore raise a dimension error; SQLite would instead score a mismatched vector as zero.

### Fixes

- Added provider compatibility fingerprints. Hash includes its configured model and dimensions; Ollama includes provider, model, and normalized base URL. `ingestion_history` now persists the fingerprint, including a migration that marks legacy rows incompatible.
- Added persisted local-index fingerprint metadata. Each collection records its successful fingerprint, and the compatibility gate checks the complete local index because the Chroma store is physically shared. Ingest, QueryEngine, CLI query, and MCP query reject an incompatible configuration with a clear `re-index required` error before any vector write or query; no existing index data is deleted on a mismatch.
- The compatibility check covers the complete local index because Chroma uses one physical collection for all logical collections. A successful Hash index in one collection therefore safely blocks an Ollama write/query in another until the index is explicitly rebuilt.
- Deleting the final successful history record for a collection removes that collection's metadata; failed history records do not prevent an explicitly emptied local index from being rebuilt. When the Chroma index is empty, its physical collection is recreated before the next ingest/query so its old dimension cannot leak into the rebuilt index.
- Added `RAG_MCP_RUNTIME_ROOT` to the three CLI scripts so an isolated Hash-configured runtime root can be exercised by real subprocesses without Ollama.
- Updated the README with default Ollama/BGE-M3 prerequisites, explicit Hash/offline and Canary behavior, and the required explicit full-index delete/re-ingest procedure for configuration switches.

### Tests

- RED/GREEN: unchanged-source provider fingerprint switching; legacy SQLite history migration; Hash and Ollama model fingerprints.
- RED/GREEN: no-network, different-dimension fake providers across SQLite and installed Chroma. Configuration changes now block ingest/query without deleting either the vector or sparse records; same configuration remains idempotent.
- RED/GREEN: Chroma can be explicitly emptied and then safely queried/re-ingested with a new vector dimension.
- RED/GREEN: multi-collection index compatibility blocks a changed provider across logical collections, avoiding Chroma dimension errors and SQLite zero-score mixing.
- RED/GREEN: actual `python scripts/ingest.py`, `query.py`, and `delete_document.py` subprocess smoke from the `rag-mcp` root with a temporary explicit Hash runtime root; the query CLI also reports `re-index required` after a configuration change.
- Focused final suite: `38 passed in 4.97s`.

### Risks

- Provider/model changes now require an operator to explicitly delete all indexed sources across the local runtime and ingest them again. This is intentional: silent deletion or mixed embedding spaces would be unsafe.
- Legacy history rows are conservatively treated as incompatible and require the same explicit rebuild.
