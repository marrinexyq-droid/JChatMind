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
from src.mcp_server import server as server_module


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
        history_db=tmp_path / "history.db",
    )
    return KnowledgeHub(engine, vector_store), str(result.document_id)


def test_mcp_server_lists_tools_and_calls_query(tmp_path):
    hub, _ = build_hub(tmp_path)
    server = JsonRpcMcpServer(hub)

    tools = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in tools["result"]["tools"]}

    assert {
        "query_knowledge_hub",
        "list_collections",
        "get_system_status",
        "get_document_summary",
    } <= names

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
    payload = result["structuredContent"]
    assert payload["result_count"] == 1
    assert "MCP tools expose" in payload["citations"][0]["text"]
    assert payload["trace_id"]
    stages = {stage["name"]: stage for stage in payload["trace_stages"]}
    assert {"query_processing", "dense_retrieval", "sparse_retrieval", "fusion", "response_build"} <= set(stages)
    assert stages["dense_retrieval"]["details"]["results"][0]["chunk_id"]
    assert stages["sparse_retrieval"]["details"]["results"][0]["chunk_id"]
    assert stages["response_build"]["details"]["results"][0]["citation_id"] == "C1"
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


def test_mcp_server_reports_system_status(tmp_path):
    hub, _ = build_hub(tmp_path)
    server = JsonRpcMcpServer(hub)

    response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_system_status", "arguments": {}},
        }
    )

    payload = response["result"]["structuredContent"]
    assert payload["status"] == "ready"
    assert payload["collections"] == ["mcp-test"]
    assert payload["collection_chunk_counts"] == {"mcp-test": 1}
    assert payload["total_chunks"] == 1


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


def test_mcp_server_reports_reindex_required_for_incompatible_embedding_settings(tmp_path):
    source = tmp_path / "mcp.md"
    source.write_text("# MCP RAG\n\nOld embedding dimension.", encoding="utf-8")
    history_db = tmp_path / "history.db"
    vector_store = SqliteVectorStore(tmp_path / "vectors.db")
    sparse_index = SqliteSparseIndex(tmp_path / "sparse.db")
    old_provider = HashEmbeddingProvider(dimensions=2, model="legacy")
    new_provider = HashEmbeddingProvider(dimensions=3, model="replacement")
    IngestionPipeline(
        history_db=history_db,
        vector_store=vector_store,
        sparse_index=sparse_index,
        embedding_provider=old_provider,
    ).run(source, collection="mcp-test")
    hub = KnowledgeHub(
        QueryEngine(
            vector_store=vector_store,
            sparse_index=sparse_index,
            embedding_provider=new_provider,
            history_db=history_db,
        ),
        vector_store,
    )
    server = JsonRpcMcpServer(hub)

    response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "query_knowledge_hub",
                "arguments": {"query": "embedding", "collection": "mcp-test"},
            },
        }
    )

    assert response["error"]["code"] == -32603
    assert "re-index required" in response["error"]["message"]


def test_build_local_hub_uses_llm_settings_for_answer_generation(monkeypatch, tmp_path):
    settings = server_module.Settings.model_validate(
        {
            "app_name": "test-rag-mcp",
            "storage": {
                "vector_store_backend": "sqlite",
                "chroma_path": "data/db/chroma",
                "bm25_path": "data/db/bm25",
                "ingestion_history_db": "data/db/ingestion_history.db",
                "image_index_db": "data/db/image_index.db",
                "traces_path": "logs/traces.jsonl",
            },
            "embedding": {"provider": "hash", "model": "hash", "base_url": ""},
            "llm": {
                "provider": "ollama",
                "model": "llama3.2",
                "base_url": "http://ollama.local:11434",
            },
            "retrieval": {},
            "evaluation": {"baseline_report": "output/report.md", "metrics_dir": "output/metrics"},
        }
    )
    observed = []

    class FixedLLM:
        def generate(self, prompt: str) -> str:
            return "Configured answer [C1]."

    monkeypatch.setattr(
        server_module.Settings,
        "load",
        classmethod(lambda _cls, _path: settings),
    )
    monkeypatch.setattr(
        server_module,
        "build_llm_provider",
        lambda llm_settings: observed.append(llm_settings) or FixedLLM(),
    )

    hub = server_module.build_local_hub(tmp_path)

    assert observed == [settings.llm]
    assert hub.query_engine.answer_generator is not None


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
