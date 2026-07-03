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

Version 1.0 is complete when tests pass and the evaluation script reports whether
the existing Java RAG baseline report and the optional `ragas` package are
available in the local environment.
