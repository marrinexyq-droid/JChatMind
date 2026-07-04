from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from src.core.query_engine import QueryEngine
from src.core.settings import Settings
from src.libs.embeddings import HashEmbeddingProvider
from src.libs.rerankers import build_reranker
from src.mcp_server.tools import KnowledgeHub, ToolPayload
from src.observability.trace_writer import JsonlTraceWriter
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "query_knowledge_hub",
        "description": "Search indexed JChatMind knowledge and return cited evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "default": 5},
                "collection": {"type": "string", "default": "default"},
                "mode": {
                    "type": "string",
                    "enum": ["vector", "hybrid", "hybrid-rerank"],
                    "default": "hybrid",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_collections",
        "description": "List collections available in the local rag-mcp index.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_document_summary",
        "description": "Return a compact summary and metadata for one indexed document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "collection": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "default": 1200},
            },
            "required": ["doc_id"],
        },
    },
]


class JsonRpcMcpServer:
    def __init__(self, hub: KnowledgeHub):
        self.hub = hub

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = str(message.get("method", ""))
        if request_id is None and method.startswith("notifications/"):
            return None

        try:
            params = message.get("params")
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ValueError as exc:
            return _error_response(request_id, -32602, str(exc))
        except Exception as exc:
            return _error_response(request_id, -32603, str(exc))

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": str(params.get("protocolVersion", "2024-11-05")),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "jchatmind-rag-mcp", "version": "1.2.0"},
            }
        if method == "tools/list":
            return {"tools": TOOL_SCHEMAS}
        if method == "tools/call":
            return _tool_result(self._call_tool(params))
        raise ValueError(f"unsupported method: {method}")

    def _call_tool(self, params: dict[str, Any]) -> ToolPayload:
        name = str(params.get("name", ""))
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")

        if name == "query_knowledge_hub":
            mode = str(arguments.get("mode", "hybrid"))
            if mode not in {"vector", "hybrid", "hybrid-rerank"}:
                raise ValueError(f"unsupported retrieval mode: {mode}")
            return self.hub.query_knowledge_hub(
                query=str(arguments.get("query", "")),
                top_k=arguments.get("top_k", 5),
                collection=_string_argument(arguments.get("collection"), "default"),
                mode=mode,
            )
        if name == "list_collections":
            return self.hub.list_collections()
        if name == "get_document_summary":
            return self.hub.get_document_summary(
                doc_id=str(arguments.get("doc_id", "")),
                collection=_optional_string(arguments.get("collection")),
                max_chars=arguments.get("max_chars", 1200),
            )
        raise ValueError(f"unsupported tool: {name}")


def build_local_hub(project_root: Path) -> KnowledgeHub:
    settings = Settings.load(project_root / "config/settings.yaml")
    provider = HashEmbeddingProvider()
    vector_store = SqliteVectorStore(project_root / settings.storage.vector_store_db)
    sparse_index = SqliteSparseIndex(project_root / settings.storage.bm25_path)
    engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
        reranker=build_reranker(
            settings.retrieval.rerank_backend,
            base_url=settings.retrieval.reranker_base_url,
            timeout_seconds=settings.retrieval.reranker_timeout_seconds,
        ),
        trace_writer=JsonlTraceWriter(project_root / settings.storage.traces_path),
        rrf_k=settings.retrieval.rrf_k,
        candidate_pool_size=settings.retrieval.candidate_pool_size,
    )
    return KnowledgeHub(query_engine=engine, vector_store=vector_store)


def serve_stdio(
    server: JsonRpcMcpServer,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("request must be a JSON object")
            response = server.handle_message(message)
        except Exception as exc:
            print(f"rag-mcp stdio parse error: {exc}", file=stderr)
            response = _error_response(None, -32700, "invalid JSON-RPC request")

        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


def _tool_result(payload: ToolPayload) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": payload.text}],
        "structuredContent": payload.data,
        "isError": False,
    }


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _string_argument(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
