# Task 6 Report: evidence-grounded LLM answer generation

## Commit

`HEAD` — `feat: generate cited answers from retrieved evidence`

## RED / GREEN

- RED: `AnswerGenerator` import failed before the new generator existed; the first valid-citation test passed after the minimal implementation.
- RED: unknown and omitted citations returned the LLM text; both now fall back to the stable evidence answer.
- RED: empty evidence called the LLM; it now returns `No evidence found.` without making a model call.
- RED: the prompt lacked the grounding, citation, and insufficiency requirements; the generated prompt now includes all three and the cited evidence.
- RED: no LLM provider/settings existed; the factory now uses configured Ollama model, URL, and timeout.
- RED: Ollama generation exposed raw transport errors and lacked response validation; HTTP/transport/response errors are now safe, classified messages with no API-key contents.
- RED: `QueryEngine` did not accept an answer generator, did not fall back after failures, and did not mark invalid citations as fallback; all paths now return the existing evidence text and emit an `answer_generation` trace stage.
- RED: MCP and the query CLI did not construct the answer generator from `llm` settings; both now do, while settings without `llm` retain evidence-only behavior.

## Implementation

- Added `BaseLLMProvider`, an Ollama `/api/generate` adapter, and a settings-based provider factory. The only optional key is read from `OLLAMA_API_KEY`; it is never serialized to config or propagated in adapter errors.
- Added `AnswerGenerator`, which supplies a grounded prompt, requires returned citation markers to be present in the retrieved evidence, and returns evidence-only fallback text for invalid/no citations or no evidence.
- Added `LlmSettings` plus the default local Ollama configuration (`llama3.2`); a missing `llm` section remains an explicit evidence-only configuration.
- `QueryEngine` keeps the task-4 local-index integrity validation before retrieval and model generation. Its `SearchResponse(answer_text, results)` contract is unchanged. Generation failures use the existing evidence renderer and write `fallback: true` without serializing the original exception.
- MCP local-hub construction and `scripts/query.py` inject the configuration-selected generator. Existing `KnowledgeHub` payload and Java/MCP-compatible answer fields remain unchanged.
- Task-5 ingestion progress/callback code was not modified.

## Verification

- Baseline before changes: `uv run pytest -q` — 121 passed.
- `uv run pytest tests/core/test_answer_generator.py tests/core/test_query_engine.py tests/mcp_server/test_server.py -q` — 21 passed.
- `uv run pytest tests/libs/test_llms.py tests/core/test_settings.py tests/integration/test_cli_scripts.py tests/integration/test_ingestion_query_flow.py -q` — 36 passed.
- `uv run pytest -q` — 136 passed.
- `git diff --check` — passed.

## Scope

- `progress.md` was deliberately not modified.
- A separate reviewer could not be dispatched because all agent slots were occupied; the implementation was instead checked against the task brief, focused tests, full suite, and `git diff --check`.
