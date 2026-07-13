from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.settings import Settings
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embedding_factory import build_embedding_provider
from src.mcp_server.server import JsonRpcMcpServer, build_local_hub
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import build_vector_store


REQUIRED_TOOLS = {
    "query_knowledge_hub",
    "list_collections",
    "get_system_status",
    "get_document_summary",
}


def run_canary(
    project_root: Path,
    collection: str = "canary",
    *,
    require_chroma: bool = False,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    _ensure_empty_project_root(project_root)
    _prepare_project_root(project_root)
    settings = Settings.load(project_root / "config/settings.yaml")
    source = project_root / "data/documents/canary.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Canary RAG Bridge\n\n"
        "The canary bridge validates MCP readiness, hybrid retrieval, cited evidence, "
        "document summaries, and query traces before Java traffic is cut over.",
        encoding="utf-8",
    )

    provider = build_embedding_provider(settings.embedding)
    vector_store = build_vector_store(project_root, settings.storage)
    actual_backend = vector_store.__class__.__name__
    if require_chroma and actual_backend != "ChromaVectorStore":
        raise AssertionError(
            "canary requires ChromaVectorStore but resolved "
            f"{actual_backend}; install rag-mcp[chroma] or disable fallback"
        )
    pipeline = IngestionPipeline(
        history_db=project_root / settings.storage.ingestion_history_db,
        vector_store=vector_store,
        sparse_index=SqliteSparseIndex(project_root / settings.storage.bm25_path),
        embedding_provider=provider,
        trace_writer=JsonlTraceWriter(project_root / settings.storage.traces_path),
    )
    ingestion = pipeline.run(source, collection=collection)
    if ingestion.status != "ingested" or not ingestion.document_id:
        raise AssertionError(f"canary ingestion failed: {ingestion}")

    server = JsonRpcMcpServer(build_local_hub(project_root))
    initialize = _must_handle(
        server,
        {"jsonrpc": "2.0", "id": "canary-initialize", "method": "initialize"},
    )
    tools = _must_handle(server, {"jsonrpc": "2.0", "id": "canary-tools", "method": "tools/list"})
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    missing = sorted(REQUIRED_TOOLS - tool_names)
    if missing:
        raise AssertionError(f"canary missing MCP tools: {missing}")

    status = _must_tool_call(server, "canary-status", "get_system_status", {})
    status_payload = status["result"]["structuredContent"]
    if status_payload["status"] != "ready":
        raise AssertionError(f"canary status is not ready: {status_payload}")
    if collection not in status_payload["collections"]:
        raise AssertionError(f"canary collection not visible: {status_payload}")
    if status_payload["total_chunks"] < ingestion.chunk_count:
        raise AssertionError(f"canary chunk count mismatch: {status_payload}")

    query = _must_tool_call(
        server,
        "canary-query",
        "query_knowledge_hub",
        {
            "query": "MCP readiness hybrid retrieval cited evidence traces",
            "collection": collection,
            "top_k": 2,
            "mode": "hybrid",
        },
    )
    query_payload = query["result"]["structuredContent"]
    citations = query_payload["citations"]
    if query_payload["result_count"] < 1 or not citations:
        raise AssertionError(f"canary query returned no citations: {query_payload}")
    if "Evidence found:" not in query["result"]["content"][0]["text"]:
        raise AssertionError("canary query did not return evidence text")

    summary = _must_tool_call(
        server,
        "canary-summary",
        "get_document_summary",
        {"doc_id": ingestion.document_id, "collection": collection},
    )
    summary_payload = summary["result"]["structuredContent"]
    if summary_payload["document_id"] != ingestion.document_id:
        raise AssertionError(f"canary summary mismatch: {summary_payload}")

    traces = _trace_counts(project_root / settings.storage.traces_path)
    if traces.get("ingestion", 0) < 1 or traces.get("query", 0) < 1:
        raise AssertionError(f"canary traces missing: {traces}")

    return {
        "status": "passed",
        "project_root": str(project_root),
        "collection": collection,
        "document_id": ingestion.document_id,
        "chunk_count": ingestion.chunk_count,
        "vector_store": {
            "configured_backend": settings.storage.vector_store_backend,
            "actual_backend": actual_backend,
            "chroma_required": require_chroma,
        },
        "mcp": {
            "server_name": initialize["result"]["serverInfo"]["name"],
            "server_version": initialize["result"]["serverInfo"]["version"],
            "tools": sorted(tool_names),
            "status": status_payload,
        },
        "query": {
            "result_count": query_payload["result_count"],
            "citation_ids": [citation["citation_id"] for citation in citations],
            "chunk_ids": [citation["chunk_id"] for citation in citations],
        },
        "summary": {
            "title": summary_payload["title"],
            "chunk_count": summary_payload["chunk_count"],
        },
        "traces": traces,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run an isolated rag-mcp canary smoke test.")
    parser.add_argument("--collection", default="canary")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--require-chroma", action="store_true")
    args = parser.parse_args()

    if args.workdir is not None:
        report = run_canary(
            args.workdir,
            collection=args.collection,
            require_chroma=args.require_chroma,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.keep_workdir:
        workdir = Path(tempfile.mkdtemp(prefix="rag-mcp-canary-"))
        report = run_canary(
            workdir,
            collection=args.collection,
            require_chroma=args.require_chroma,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    workdir = Path(tempfile.mkdtemp(prefix="rag-mcp-canary-"))
    try:
        report = run_canary(
            workdir,
            collection=args.collection,
            require_chroma=args.require_chroma,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


def _prepare_project_root(project_root: Path) -> None:
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "settings.yaml").write_text(
        """
app_name: rag-mcp-canary

storage:
  vector_store_backend: chroma
  sqlite_fallback_when_chroma_unavailable: true
  chroma_path: data/db/chroma
  vector_store_db: data/db/vector_store.db
  bm25_path: data/db/bm25
  ingestion_history_db: data/db/ingestion_history.db
  image_index_db: data/db/image_index.db
  traces_path: logs/traces.jsonl

embedding:
  provider: hash
  model: hash
  base_url: ""

retrieval:
  rrf_k: 60
  default_top_k: 5
  candidate_pool_size: 20
  rerank_backend: none
  reranker_base_url: http://127.0.0.1:8001
  reranker_timeout_seconds: 8.0

evaluation:
  baseline_report: output/rag_eval_report.md
  metrics_dir: output/metrics
""".lstrip(),
        encoding="utf-8",
    )


def _ensure_empty_project_root(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    if any(project_root.iterdir()):
        raise ValueError(f"canary project root must be empty: {project_root}")


def _must_handle(server: JsonRpcMcpServer, message: dict[str, Any]) -> dict[str, Any]:
    response = server.handle_message(message)
    if response is None:
        raise AssertionError(f"canary request produced no response: {message}")
    if "error" in response:
        raise AssertionError(f"canary MCP error: {response['error']}")
    return response


def _must_tool_call(
    server: JsonRpcMcpServer,
    request_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return _must_handle(
        server,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def _trace_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        trace_type = str(payload.get("trace_type", "unknown"))
        counts[trace_type] = counts.get(trace_type, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
