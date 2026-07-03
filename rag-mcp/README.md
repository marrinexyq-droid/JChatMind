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
