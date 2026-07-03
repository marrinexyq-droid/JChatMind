from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.core.query_engine import QueryEngine
from src.ingestion.pipeline import IngestionPipeline
from src.libs.embeddings import HashEmbeddingProvider
from src.mcp_server.server import JsonRpcMcpServer
from src.mcp_server.tools import KnowledgeHub
from src.storage.sparse_index import SqliteSparseIndex
from src.storage.vector_store import SqliteVectorStore


def build_hub(tmp_path: Path) -> tuple[KnowledgeHub, str]:
    source = tmp_path / "mcp.md"
    source.write_text(
        "# MCP RAG\n\nMCP tools expose hybrid retrieval with citations.",
        encoding="utf-8",
    )
    provider = HashEmbeddingProvider(dimensions=64)
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    pipeline = IngestionPipeline(
        history_db=tmp_path / "history.db",
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    result = pipeline.run(source, collection="mcp-test")
    engine = QueryEngine(
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=provider,
    )
    return KnowledgeHub(engine, vector_store), str(result.document_id)


def test_mcp_server_lists_tools_and_calls_query(tmp_path):
    hub, _ = build_hub(tmp_path)
    server = JsonRpcMcpServer(hub)

    tools = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in tools["result"]["tools"]}

    assert {"query_knowledge_hub", "list_collections", "get_document_summary"} <= names

    response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "query_knowledge_hub",
                "arguments": {
                    "query": "hybrid retrieval citations",
                    "collection": "mcp-test",
                    "top_k": 1,
                },
            },
        }
    )

    result = response["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["result_count"] == 1
    assert "Evidence found:" in result["content"][0]["text"]


def test_mcp_server_lists_collections_and_summarizes_document(tmp_path):
    hub, document_id = build_hub(tmp_path)
    server = JsonRpcMcpServer(hub)

    collections = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_collections", "arguments": {}},
        }
    )
    assert collections["result"]["structuredContent"]["collections"] == ["mcp-test"]

    summary = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_document_summary",
                "arguments": {"doc_id": document_id, "collection": "mcp-test"},
            },
        }
    )
    payload = summary["result"]["structuredContent"]
    assert payload["document_id"] == document_id
    assert payload["chunk_count"] == 1
    assert "MCP tools expose" in payload["preview"]


def test_mcp_server_rejects_invalid_params_and_retrieval_mode(tmp_path):
    hub, _ = build_hub(tmp_path)
    server = JsonRpcMcpServer(hub)

    bad_params = server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": []}
    )
    assert bad_params["error"]["code"] == -32602

    bad_arguments = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_collections", "arguments": []},
        }
    )
    assert bad_arguments["error"]["code"] == -32602

    bad_mode = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "query_knowledge_hub",
                "arguments": {"query": "citations", "mode": "keyword-only"},
            },
        }
    )
    assert bad_mode["error"]["code"] == -32602


def test_mcp_main_speaks_json_rpc_over_stdio():
    repo_root = Path(__file__).resolve().parents[3]
    request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/list",
    }

    process = subprocess.run(
        [sys.executable, str(repo_root / "rag-mcp/main.py")],
        cwd=repo_root,
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0
    response = json.loads(process.stdout.splitlines()[0])
    assert response["id"] == 7
    assert "tools" in response["result"]
