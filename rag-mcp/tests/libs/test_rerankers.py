from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.core.types import RetrievalResult
from src.libs.rerankers import HttpReranker, NoopReranker, build_reranker


def test_http_reranker_posts_documents_and_reorders_by_score():
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            received["path"] = self.path
            received["payload"] = json.loads(self.rfile.read(length).decode("utf-8"))
            body = json.dumps(
                [
                    {"index": 1, "score": 0.91},
                    {"index": 0, "score": 0.42},
                    {"index": 10, "score": 1.0},
                    {"index": "bad", "score": 1.0},
                ]
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        reranker = HttpReranker(
            base_url=f"http://127.0.0.1:{server.server_port}",
            timeout_seconds=2.0,
        )
        results = reranker.rerank(
            "which document wins?",
            [
                _candidate("c1", "first document"),
                _candidate("c2", "second document"),
            ],
            top_k=2,
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert received["path"] == "/rerank"
    assert received["payload"] == {
        "query": "which document wins?",
        "documents": ["first document", "second document"],
    }
    assert [result.chunk_id for result in results] == ["c2", "c1"]
    assert [result.score for result in results] == [0.91, 0.42]
    assert {result.source for result in results} == {"rerank"}


def test_build_reranker_keeps_none_default_and_rejects_unknown_backend():
    assert build_reranker("none") is None
    assert isinstance(build_reranker("noop"), NoopReranker)
    assert isinstance(build_reranker("http"), HttpReranker)
    with pytest.raises(ValueError, match="unsupported rerank backend"):
        build_reranker("cross-encoder")


def _candidate(chunk_id: str, text: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        text=text,
        score=0.0,
        source="candidate",
    )
