# RAG DEV_SPEC Replacement 1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build version 1.0 of the Python `rag-mcp` replacement spine for JChatMind RAG, with project structure, core contracts, trace logging, a retrieval evaluation harness, and runnable entrypoints ready for ingestion/query/MCP implementation.

**Architecture:** Version 1.0 creates a Python-first RAG subsystem beside the existing Java app. It establishes the deep module interfaces from the DEV_SPEC replacement design first, then adds an evaluation harness so each later ingestion/query change can be measured before Java RAG is retired.

**Tech Stack:** Python 3.11+, pytest, pydantic, PyYAML, SQLite, JSON Lines, optional ragas import check, existing `jchatmind/reranker-service/rag_eval` output as baseline.

---

## Version

Plan version: `1.0`

Design source:

- `docs/superpowers/specs/2026-07-03-rag-dev-spec-replacement-design.md`
- `C:/Users/Xyq/Downloads/DEV_SPEC.md`

## File Structure

Create the new Python subsystem under `rag-mcp/`:

```text
rag-mcp/
  config/
    settings.yaml
  src/
    __init__.py
    core/
      __init__.py
      types.py
      settings.py
      query_engine.py
    observability/
      __init__.py
      trace_context.py
      trace_writer.py
    evaluation/
      __init__.py
      metrics.py
      runner.py
      ragas_selftest.py
  scripts/
    evaluate.py
  tests/
    core/
      test_settings.py
      test_types.py
    observability/
      test_trace_context.py
    evaluation/
      test_metrics.py
      test_ragas_selftest.py
  pyproject.toml
  README.md
```

Do not modify the current Java RAG behavior in version 1.0. Java integration starts only after the Python subsystem has measurable ingestion/query behavior.

## Task 1: Python Project Skeleton

**Files:**

- Create: `rag-mcp/pyproject.toml`
- Create: `rag-mcp/README.md`
- Create: `rag-mcp/src/__init__.py`
- Create: `rag-mcp/src/core/__init__.py`
- Create: `rag-mcp/src/observability/__init__.py`
- Create: `rag-mcp/src/evaluation/__init__.py`
- Create: `rag-mcp/tests/core/test_settings.py`

- [ ] **Step 1: Write the failing settings import test**

Create `rag-mcp/tests/core/test_settings.py`:

```python
from pathlib import Path

from src.core.settings import Settings


def test_loads_default_settings_file():
    settings = Settings.load(Path("config/settings.yaml"))

    assert settings.app_name == "rag-mcp"
    assert settings.storage.chroma_path == "data/db/chroma"
    assert settings.evaluation.baseline_report.endswith("rag_eval_report.md")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd rag-mcp
python -m pytest tests/core/test_settings.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `src.core.settings`.

- [ ] **Step 3: Add project metadata**

Create `rag-mcp/pyproject.toml`:

```toml
[project]
name = "rag-mcp"
version = "1.0.0"
description = "Python MCP RAG replacement subsystem for JChatMind"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7",
  "PyYAML>=6.0",
  "pytest>=8.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Add README**

Create `rag-mcp/README.md`:

```markdown
# rag-mcp

Version 1.0 of the Python RAG replacement subsystem for JChatMind.

This project starts as a measured replacement spine. It owns Python-side
contracts, trace logging, and evaluation harnesses before becoming the canonical
ingestion and query implementation.

Run tests:

```bash
python -m pytest -q
```
```

- [ ] **Step 5: Add package markers**

Create empty files:

```text
rag-mcp/src/__init__.py
rag-mcp/src/core/__init__.py
rag-mcp/src/observability/__init__.py
rag-mcp/src/evaluation/__init__.py
```

- [ ] **Step 6: Commit**

Run:

```bash
git add rag-mcp/pyproject.toml rag-mcp/README.md rag-mcp/src rag-mcp/tests/core/test_settings.py
git commit -m "feat(rag-mcp): scaffold python replacement project"
```

## Task 2: Settings Module

**Files:**

- Create: `rag-mcp/config/settings.yaml`
- Create: `rag-mcp/src/core/settings.py`
- Modify: `rag-mcp/tests/core/test_settings.py`

- [ ] **Step 1: Add default settings**

Create `rag-mcp/config/settings.yaml`:

```yaml
app_name: rag-mcp

storage:
  chroma_path: data/db/chroma
  bm25_path: data/db/bm25
  ingestion_history_db: data/db/ingestion_history.db
  image_index_db: data/db/image_index.db
  traces_path: logs/traces.jsonl

embedding:
  provider: ollama
  model: bge-m3
  base_url: http://localhost:11434

retrieval:
  rrf_k: 60
  default_top_k: 5
  candidate_pool_size: 20
  rerank_backend: none

evaluation:
  baseline_report: ../jchatmind/reranker-service/rag_eval/output/rag_eval_report.md
  metrics_dir: output/metrics
```

- [ ] **Step 2: Implement settings loader**

Create `rag-mcp/src/core/settings.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class StorageSettings(BaseModel):
    chroma_path: str
    bm25_path: str
    ingestion_history_db: str
    image_index_db: str
    traces_path: str


class EmbeddingSettings(BaseModel):
    provider: str
    model: str
    base_url: str


class RetrievalSettings(BaseModel):
    rrf_k: int = 60
    default_top_k: int = 5
    candidate_pool_size: int = 20
    rerank_backend: str = "none"


class EvaluationSettings(BaseModel):
    baseline_report: str
    metrics_dir: str


class Settings(BaseModel):
    app_name: str
    storage: StorageSettings
    embedding: EmbeddingSettings
    retrieval: RetrievalSettings
    evaluation: EvaluationSettings

    @classmethod
    def load(cls, path: Path) -> "Settings":
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.model_validate(raw)
```

- [ ] **Step 3: Expand settings tests**

Modify `rag-mcp/tests/core/test_settings.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.settings import Settings


def test_loads_default_settings_file():
    settings = Settings.load(Path("config/settings.yaml"))

    assert settings.app_name == "rag-mcp"
    assert settings.storage.chroma_path == "data/db/chroma"
    assert settings.evaluation.baseline_report.endswith("rag_eval_report.md")


def test_rejects_missing_storage_section(tmp_path):
    config = tmp_path / "settings.yaml"
    config.write_text("app_name: rag-mcp\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        Settings.load(config)
```

- [ ] **Step 4: Run settings tests**

Run:

```bash
cd rag-mcp
python -m pytest tests/core/test_settings.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add rag-mcp/config/settings.yaml rag-mcp/src/core/settings.py rag-mcp/tests/core/test_settings.py
git commit -m "feat(rag-mcp): add settings loader"
```

## Task 3: Core Data Contracts

**Files:**

- Create: `rag-mcp/src/core/types.py`
- Create: `rag-mcp/tests/core/test_types.py`

- [ ] **Step 1: Write contract tests**

Create `rag-mcp/tests/core/test_types.py`:

```python
from src.core.types import ChunkRecord, Document, RetrievalResult, SearchRequest


def test_chunk_record_has_stable_text_for_embedding():
    chunk = ChunkRecord(
        id="doc1-0001-abc",
        document_id="doc1",
        collection="default",
        text="body",
        metadata={"title": "Heading"},
    )

    assert chunk.embedding_text() == "Heading\nbody"


def test_search_request_defaults():
    request = SearchRequest(query="What is RAG?")

    assert request.collection == "default"
    assert request.top_k == 5
    assert request.mode == "hybrid"


def test_retrieval_result_keeps_citation_id():
    result = RetrievalResult(
        chunk_id="c1",
        document_id="d1",
        text="evidence",
        score=0.9,
        source="hybrid",
        citation_id="C1",
    )

    assert result.citation_id == "C1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd rag-mcp
python -m pytest tests/core/test_types.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `src.core.types`.

- [ ] **Step 3: Implement core types**

Create `rag-mcp/src/core/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RetrievalMode = Literal["vector", "hybrid", "hybrid-rerank"]


@dataclass(frozen=True)
class Document:
    id: str
    collection: str
    source_path: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    document_id: str
    collection: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def embedding_text(self) -> str:
        title = str(self.metadata.get("title", "")).strip()
        body = self.text.strip()
        return f"{title}\n{body}".strip() if title else body


@dataclass(frozen=True)
class SearchRequest:
    query: str
    collection: str = "default"
    top_k: int = 5
    mode: RetrievalMode = "hybrid"


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    citation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run core type tests**

Run:

```bash
cd rag-mcp
python -m pytest tests/core/test_types.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add rag-mcp/src/core/types.py rag-mcp/tests/core/test_types.py
git commit -m "feat(rag-mcp): define core RAG contracts"
```

## Task 4: TraceContext and JSONL Writer

**Files:**

- Create: `rag-mcp/src/observability/trace_context.py`
- Create: `rag-mcp/src/observability/trace_writer.py`
- Create: `rag-mcp/tests/observability/test_trace_context.py`

- [ ] **Step 1: Write trace tests**

Create `rag-mcp/tests/observability/test_trace_context.py`:

```python
import json

from src.observability.trace_context import TraceContext
from src.observability.trace_writer import JsonlTraceWriter


def test_trace_context_serializes_stage_details():
    trace = TraceContext(trace_type="query", inputs={"query": "rag"})
    trace.record_stage("dense_retrieval", method="chroma", provider="ollama", details={"count": 3}, elapsed_ms=12.5)
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd rag-mcp
python -m pytest tests/observability/test_trace_context.py -v
```

Expected: FAIL with missing observability modules.

- [ ] **Step 3: Implement trace context**

Create `rag-mcp/src/observability/trace_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class TraceContext:
    trace_type: str
    inputs: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    stages: list[dict[str, Any]] = field(default_factory=list)

    def record_stage(
        self,
        name: str,
        method: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
        elapsed_ms: float | None = None,
    ) -> None:
        self.stages.append(
            {
                "name": name,
                "method": method,
                "provider": provider,
                "details": details or {},
                "elapsed_ms": elapsed_ms,
            }
        )

    def finish(self, error: str | None = None) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "trace_type": self.trace_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": self.inputs,
            "stages": self.stages,
            "error": error,
        }
```

- [ ] **Step 4: Implement JSONL writer**

Create `rag-mcp/src/observability/trace_writer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonlTraceWriter:
    def __init__(self, path: Path):
        self.path = path

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 5: Run trace tests**

Run:

```bash
cd rag-mcp
python -m pytest tests/observability/test_trace_context.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add rag-mcp/src/observability rag-mcp/tests/observability
git commit -m "feat(rag-mcp): add trace context and jsonl writer"
```

## Task 5: Retrieval Metrics Harness

**Files:**

- Create: `rag-mcp/src/evaluation/metrics.py`
- Create: `rag-mcp/tests/evaluation/test_metrics.py`

- [ ] **Step 1: Write metric tests**

Create `rag-mcp/tests/evaluation/test_metrics.py`:

```python
from src.evaluation.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_recall_at_k_counts_ground_truth_hits():
    assert recall_at_k(["a", "b"], ["x", "a", "c"], 2) == 0.5


def test_precision_at_k_counts_top_k_hits():
    assert precision_at_k(["a", "b"], ["a", "x", "b"], 2) == 0.5


def test_mrr_returns_first_relevant_rank():
    assert mrr(["b"], ["a", "b", "c"]) == 0.5


def test_ndcg_is_one_for_ideal_order():
    assert ndcg_at_k(["a", "b"], ["a", "b"], 2) == 1.0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd rag-mcp
python -m pytest tests/evaluation/test_metrics.py -v
```

Expected: FAIL with missing `metrics.py`.

- [ ] **Step 3: Implement metrics**

Create `rag-mcp/src/evaluation/metrics.py`:

```python
from __future__ import annotations

import math


def recall_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    if not ground_truth:
        return 0.0
    hits = sum(1 for item in ground_truth if item in set(retrieved[:k]))
    return hits / len(ground_truth)


def precision_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in set(ground_truth))
    return hits / k


def mrr(ground_truth: list[str], retrieved: list[str]) -> float:
    truth = set(ground_truth)
    for index, item in enumerate(retrieved):
        if item in truth:
            return 1.0 / (index + 1)
    return 0.0


def ndcg_at_k(ground_truth: list[str], retrieved: list[str], k: int) -> float:
    truth = set(ground_truth)
    dcg = 0.0
    for index, item in enumerate(retrieved[:k]):
        relevance = 1.0 if item in truth else 0.0
        dcg += relevance / math.log2(index + 2)
    ideal_count = min(len(truth), k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_count))
    return dcg / idcg if idcg else 0.0
```

- [ ] **Step 4: Run metric tests**

Run:

```bash
cd rag-mcp
python -m pytest tests/evaluation/test_metrics.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add rag-mcp/src/evaluation/metrics.py rag-mcp/tests/evaluation/test_metrics.py
git commit -m "feat(rag-mcp): add retrieval metric functions"
```

## Task 6: Ragas Self-Test Probe

**Files:**

- Create: `rag-mcp/src/evaluation/ragas_selftest.py`
- Create: `rag-mcp/tests/evaluation/test_ragas_selftest.py`

- [ ] **Step 1: Write self-test probe tests**

Create `rag-mcp/tests/evaluation/test_ragas_selftest.py`:

```python
from src.evaluation.ragas_selftest import check_ragas_available


def test_check_ragas_available_returns_status_dict():
    status = check_ragas_available()

    assert "available" in status
    assert "message" in status
```

- [ ] **Step 2: Implement ragas availability probe**

Create `rag-mcp/src/evaluation/ragas_selftest.py`:

```python
from __future__ import annotations

import importlib.util


def check_ragas_available() -> dict[str, str | bool]:
    spec = importlib.util.find_spec("ragas")
    if spec is None:
        return {
            "available": False,
            "message": "ragas is not installed in this Python environment",
        }
    return {
        "available": True,
        "message": "ragas is importable",
    }
```

- [ ] **Step 3: Run self-test probe**

Run:

```bash
cd rag-mcp
python -m pytest tests/evaluation/test_ragas_selftest.py -v
```

Expected: PASS whether or not `ragas` is installed.

- [ ] **Step 4: Commit**

Run:

```bash
git add rag-mcp/src/evaluation/ragas_selftest.py rag-mcp/tests/evaluation/test_ragas_selftest.py
git commit -m "feat(rag-mcp): add ragas availability self-test"
```

## Task 7: Evaluation Runner Entry Point

**Files:**

- Create: `rag-mcp/src/evaluation/runner.py`
- Create: `rag-mcp/scripts/evaluate.py`

- [ ] **Step 1: Implement baseline report reader**

Create `rag-mcp/src/evaluation/runner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.evaluation.ragas_selftest import check_ragas_available


@dataclass(frozen=True)
class EvaluationSummary:
    baseline_report_exists: bool
    baseline_report_path: str
    ragas_available: bool
    ragas_message: str


def summarize_environment(baseline_report: Path) -> EvaluationSummary:
    ragas_status = check_ragas_available()
    return EvaluationSummary(
        baseline_report_exists=baseline_report.exists(),
        baseline_report_path=str(baseline_report),
        ragas_available=bool(ragas_status["available"]),
        ragas_message=str(ragas_status["message"]),
    )
```

- [ ] **Step 2: Implement CLI script**

Create `rag-mcp/scripts/evaluate.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.core.settings import Settings
from src.evaluation.runner import summarize_environment


def main() -> int:
    settings = Settings.load(Path("config/settings.yaml"))
    summary = summarize_environment(Path(settings.evaluation.baseline_report))
    print("RAG-MCP evaluation environment")
    print(f"baseline_report_exists={summary.baseline_report_exists}")
    print(f"baseline_report_path={summary.baseline_report_path}")
    print(f"ragas_available={summary.ragas_available}")
    print(f"ragas_message={summary.ragas_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run evaluation environment script**

Run:

```bash
cd rag-mcp
python scripts/evaluate.py
```

Expected output contains:

```text
RAG-MCP evaluation environment
baseline_report_exists=True
ragas_available=
```

- [ ] **Step 4: Commit**

Run:

```bash
git add rag-mcp/src/evaluation/runner.py rag-mcp/scripts/evaluate.py
git commit -m "feat(rag-mcp): add evaluation environment runner"
```

## Task 8: Query Engine Interface Stub

**Files:**

- Create: `rag-mcp/src/core/query_engine.py`
- Create: `rag-mcp/tests/core/test_query_engine.py`

- [ ] **Step 1: Write query engine contract test**

Create `rag-mcp/tests/core/test_query_engine.py`:

```python
from src.core.query_engine import QueryEngine
from src.core.types import SearchRequest


def test_query_engine_empty_index_returns_no_evidence():
    engine = QueryEngine()
    response = engine.search(SearchRequest(query="missing"))

    assert response.results == []
    assert response.answer_text == "No evidence found."
```

- [ ] **Step 2: Implement minimal query engine**

Create `rag-mcp/src/core/query_engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from src.core.types import RetrievalResult, SearchRequest


@dataclass(frozen=True)
class SearchResponse:
    answer_text: str
    results: list[RetrievalResult] = field(default_factory=list)


class QueryEngine:
    def search(self, request: SearchRequest) -> SearchResponse:
        if not request.query.strip():
            return SearchResponse(answer_text="No evidence found.")
        return SearchResponse(answer_text="No evidence found.")
```

- [ ] **Step 3: Run query engine test**

Run:

```bash
cd rag-mcp
python -m pytest tests/core/test_query_engine.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add rag-mcp/src/core/query_engine.py rag-mcp/tests/core/test_query_engine.py
git commit -m "feat(rag-mcp): add query engine interface"
```

## Task 9: Version 1.0 Verification

**Files:**

- Modify: `rag-mcp/README.md`

- [ ] **Step 1: Document version 1.0 verification commands**

Modify `rag-mcp/README.md`:

```markdown
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
```

- [ ] **Step 2: Run the full Python test suite**

Run:

```bash
cd rag-mcp
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run evaluation environment check**

Run:

```bash
cd rag-mcp
python scripts/evaluate.py
```

Expected: command exits with status 0 and prints baseline/Ragas availability.

- [ ] **Step 4: Commit**

Run:

```bash
git add rag-mcp/README.md
git commit -m "docs(rag-mcp): document version 1.0 verification"
```

## Version 1.0 Completion Gate

Version 1.0 is done when:

- `rag-mcp` exists as an independent Python project.
- `python -m pytest -q` passes inside `rag-mcp`.
- `python scripts/evaluate.py` reports the baseline report path.
- Ragas availability is reported explicitly.
- No Java RAG behavior has changed.

## Local Evaluation Snapshot

Generated on 2026-07-03 with the repository's current harness:

```bash
py -3 jchatmind\reranker-service\rag_eval\scripts\03_compute_metrics.py
py -3 jchatmind\reranker-service\rag_eval\scripts\04_report.py
```

Ragas availability probe:

```text
ragas_available=False
```

The current environment does not have the `ragas` package installed, and `jchatmind/reranker-service/rag_eval/requirements.txt` does not include it. Therefore version 1.0 includes a Ragas probe task, but the local self-test could only run the existing retrieval/latency harness.

Latest retrieval metrics:

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Precision@1 | MRR | NDCG@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| vector | 0.8333 | 1.0000 | 1.0000 | 1.0000 | 0.8333 | 0.9167 | 0.9385 |
| hybrid | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hybrid-rerank | 0.9333 | 1.0000 | 1.0000 | 1.0000 | 0.9333 | 0.9667 | 0.9754 |
| adaptive-rag | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

Latest latency metrics:

| Mode | P50 ms | P95 ms | Mean ms |
|---|---:|---:|---:|
| vector | 92.1 | 100.4 | 91.2 |
| hybrid | 92.8 | 101.0 | 92.0 |
| hybrid-rerank | 8390.8 | 8770.8 | 8398.6 |
| adaptive-rag | 0.0 | 0.0 | 0.0 |

Interpretation:

- `hybrid` is the best current default: Recall@1 and Precision@1 are `1.0000`, with nearly identical latency to vector-only.
- `hybrid-rerank` is currently worse than `hybrid` on this dataset and adds about `8.3s` P50 latency, so it should not be the default in version 1.0.
- `adaptive-rag` is present in evaluation configuration but has no raw results in the current harness output; its zero scores indicate missing data, not measured quality.
- True Ragas quality metrics such as faithfulness and answer relevancy are not available until the Python replacement package adds `ragas` and a configured judge model.

## Execution Handoff

Recommended execution mode:

1. Use `superpowers:subagent-driven-development` for tasks 1 through 9.
2. Review after each task.
3. Keep commits small and in the order listed.
4. After version 1.0 lands, create version 1.1 for the actual ingestion MVP.
