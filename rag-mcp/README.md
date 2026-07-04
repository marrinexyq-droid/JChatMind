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
LLM-judged RAGAS metrics such as faithfulness require a configured judge model.

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

The server exposes `query_knowledge_hub`, `list_collections`, and
`get_document_summary` over JSON-RPC stdio. It keeps protocol responses on
stdout so MCP clients can consume them.

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

Validate dashboard inputs without Streamlit:

```bash
python scripts/start_dashboard.py --check
```

Start the optional Streamlit dashboard:

```bash
pip install -e .[dashboard]
python scripts/start_dashboard.py
```
