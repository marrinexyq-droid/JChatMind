import json

from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter


def test_trace_context_serializes_stage_details():
    trace = TraceContext(trace_type="query", inputs={"query": "rag"})
    trace.record_stage(
        "dense_retrieval",
        method="chroma",
        provider="ollama",
        details={"count": 3},
        elapsed_ms=12.5,
    )
    payload = trace.finish()

    assert payload["trace_type"] == "query"
    assert payload["stages"][0]["name"] == "dense_retrieval"
    assert payload["stages"][0]["details"]["count"] == 3


def test_jsonl_writer_appends_one_record(tmp_path):
    path = tmp_path / "traces.jsonl"
    writer = JsonlTraceWriter(path)
    writer.write({"trace_id": "t1", "trace_type": "query", "stages": []})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["trace_id"] == "t1"
