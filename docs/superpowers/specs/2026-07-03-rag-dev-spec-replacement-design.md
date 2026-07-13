# RAG DEV_SPEC Replacement Design

Date: 2026-07-03

## Decision

JChatMind will replace the current Java/Spring RAG implementation with the
Python RAG framework described by `C:/Users/Xyq/Downloads/DEV_SPEC.md`.

The target state is not a light refactor of `RagServiceImpl`. The target state is
a new Python-first RAG subsystem that becomes the canonical implementation for
ingestion, retrieval, tracing, evaluation, dashboard management, and MCP access.
The existing Java/Spring application remains useful for chat, agents, SSE, and
the current React product surface during the transition, but Java RAG stops being
the source of truth once the Python subsystem reaches parity.

The replacement must use a strangler sequence:

1. Build the DEV_SPEC Python RAG subsystem beside the existing app.
2. Prove ingestion, retrieval, MCP, trace, dashboard, and evaluation locally.
3. Compare the new pipeline against the existing RAG baseline.
4. Switch Java chat/tool integration to call the Python RAG subsystem.
5. Remove or archive the Java RAG internals after the new path is stable.

## Current State

The current JChatMind RAG implementation is a Java/Spring Boot pipeline centered
on PostgreSQL and pgvector.

Important current modules:

- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/agent/tools/KnowledgeTools.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/DocumentFacadeServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/GraphRagServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RerankServiceImpl.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RuleBasedQueryPlanner.java`
- `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RuleBasedSelfRagEvaluator.java`
- `jchatmind/reranker-service/rag_eval`

Current query path:

```text
KnowledgeTools
  -> QueryPlanner
  -> RagServiceImpl
      -> Ollama BGE-M3 embedding call
      -> pgvector similarity search
      -> PostgreSQL tsvector BM25 search
      -> RRF fusion
      -> optional GraphRAG-lite expansion
      -> optional reranker-service call
      -> context reorder
      -> RagTrace construction
  -> SelfRagEvaluator
  -> cited tool response
```

Current ingestion path:

```text
DocumentController
  -> DocumentFacadeServiceImpl
      -> save uploaded file
      -> parse Markdown or Gemini format
      -> create heading-aware sections
      -> call RagService.embed
      -> insert ChunkBgeM3 into PostgreSQL
      -> index GraphRAG-lite entities
```

Current strengths:

- Hybrid retrieval is already implemented.
- Rerank is already available through a local Python FastAPI sidecar.
- Self-RAG evidence gating exists and is tested.
- GraphRAG-lite exists for multi-hop expansion.
- The React chat UI can render RAG traces.
- `rag_eval` contains a useful baseline for retrieval quality.

Current weaknesses relative to DEV_SPEC:

- `RagServiceImpl` is too broad. It owns embedding, retrieval, fusion, graph
  expansion, rerank orchestration, context reorder, trace construction, and
  index initialization.
- Ingestion is embedded inside `DocumentFacadeServiceImpl` instead of a reusable
  ingestion module.
- There is no unified Python-style `Document`, `Chunk`, `ChunkRecord`,
  `ProcessedQuery`, and `RetrievalResult` contract center.
- Provider seams are incomplete. Embedding, vector storage, sparse storage, and
  reranking are not all behind replaceable interfaces.
- Trace is assembled after the fact rather than recorded through a stage-based
  `TraceContext`.
- Dashboard observability is partial. React shows evidence for chat, but there is
  no local management dashboard for ingestion/query traces and data browsing.
- Incremental ingestion and file integrity checks are missing or weak.
- The Java path is tied to PostgreSQL/pgvector, while DEV_SPEC targets Chroma and
  SQLite for a local-first Python stack.

## Target State

The new canonical RAG subsystem lives in a top-level Python project:

```text
rag-mcp/
  config/
    settings.yaml
  src/
    core/
    ingestion/
    libs/
    mcp_server/
    observability/
  data/
    documents/
    images/
    db/
  cache/
    embeddings/
    captions/
    processing/
  logs/
    traces.jsonl
  tests/
  scripts/
  main.py
  pyproject.toml
  README.md
```

The `rag-mcp` project follows DEV_SPEC structure without colliding with the
existing Java `jchatmind/` or React `ui/` directories. The name makes its role
explicit: it is the MCP-facing Python RAG subsystem.

## Target Modules

### MCP Server Layer

Purpose: expose the knowledge system to MCP clients.

Interface:

- `query_knowledge_hub(query, top_k?, collection?)`
- `list_collections()`
- `get_document_summary(doc_id)`

Transport:

- JSON-RPC 2.0 over stdio.
- `stdout` is reserved for MCP protocol messages.
- logs go to `stderr` or local log files.

Initial client target:

- Claude Desktop compatible MCP.
- GitHub Copilot MCP-compatible behavior where available.

### Core Query Layer

Purpose: run query processing and retrieval behind one deep module interface.

Primary interface:

```text
QueryEngine.search(request: SearchRequest) -> SearchResponse
```

Internal modules:

- `QueryProcessor`: normalize query, extract keywords, parse filters.
- `DenseRetriever`: embed query and search Chroma.
- `SparseRetriever`: query BM25 index.
- `Fusion`: merge dense and sparse candidates by RRF.
- `Reranker`: optional cross-encoder or LLM rerank.
- `ResponseBuilder`: format MCP output with citations and optional images.

The Java `RagServiceImpl` currently exposes several retrieval-specific methods.
The Python replacement should expose fewer methods and hide more behavior behind
`QueryEngine.search`.

### Ingestion Pipeline Layer

Purpose: convert files into reusable indexed knowledge records.

Primary interface:

```text
IngestionPipeline.run(source_path, collection="default", on_progress=None)
  -> IngestionResult
```

Pipeline:

```text
FileIntegrity
  -> Loader
  -> Splitter
  -> Transform
  -> Embedding
  -> Upsert
```

Initial loader scope:

- PDF to canonical Markdown.
- Markdown direct ingestion may be included because the current project already
  depends on Markdown uploads and the existing test/evaluation content uses
  Markdown-like data.

Initial transform scope:

- rule-based cleanup
- metadata enrichment
- optional image captioning seam

The first implementation may ship image captioning as a disabled adapter if no
vision model credentials are configured. The interface must still exist.

### Libs Layer

Purpose: make variation explicit and configurable.

Initial seams and adapters:

- `BaseLLM`: OpenAI-compatible, Azure OpenAI, Ollama.
- `BaseVisionLLM`: OpenAI/Azure vision adapter, disabled fallback.
- `BaseEmbedding`: OpenAI-compatible, Ollama or local sentence-transformers.
- `BaseSplitter`: recursive Markdown-aware splitter.
- `BaseVectorStore`: Chroma.
- `BaseReranker`: none, cross-encoder adapter, LLM adapter.
- `BaseEvaluator`: custom metrics first, Ragas later.

Design rule:

- Add a seam only where at least two adapters are expected during this
  replacement. For example, Chroma can be the only vector store at first because
  DEV_SPEC names it as the default. Embedding and rerank deserve seams early
  because the current project already uses different providers.

### Storage Layer

Target storage:

- Chroma for vectors and chunk payloads.
- local BM25 index for sparse retrieval.
- SQLite `ingestion_history.db` for file hashes and ingestion status.
- SQLite `image_index.db` for image path lookup.
- local filesystem for original documents and extracted images.
- `logs/traces.jsonl` for traces.

PostgreSQL/pgvector remains available to the old Java system during transition,
but it is not part of the final Python RAG source of truth.

### Observability Layer

Purpose: make ingestion and query behavior inspectable.

Core module:

```text
TraceContext(trace_type)
  -> record_stage(name, method, provider, details, elapsed_ms)
  -> finish()
  -> to_dict()
```

Trace types:

- `ingestion`: load, split, transform, embed, upsert.
- `query`: query_processing, dense_retrieval, sparse_retrieval, fusion, rerank,
  response_build.

Dashboard:

- Overview
- Data Browser
- Ingestion Manager
- Ingestion Traces
- Query Traces
- Evaluation Panel

Streamlit is the dashboard target because that is the DEV_SPEC direction.
The existing React RAG evidence panel may remain during the transition, but it is
not the canonical management dashboard.

### Evaluation Layer

Purpose: prevent the replacement from losing retrieval quality.

Initial evaluator:

- custom retrieval metrics: Hit Rate, Recall@K, MRR, NDCG@K, latency.

Later evaluator:

- Ragas for faithfulness and answer relevancy once generation is included.

Baseline:

- Use `jchatmind/reranker-service/rag_eval` as the first source of labeled
  retrieval data.
- The Python pipeline must be measured against the current `vector`, `hybrid`,
  and `hybrid-rerank` baseline before the Java path is retired.

Minimum cutover criteria:

- Python hybrid Recall@1 is not materially worse than current Java hybrid.
- Python hybrid-rerank MRR is not materially worse than current Java
  hybrid-rerank.
- The pipeline returns citations with stable chunk IDs.
- The MCP tool can run end-to-end from a subprocess test.
- Ingestion and query traces are visible in JSONL and dashboard pages.

## Replacement Strategy

### Phase 1: Scaffold Python Subsystem

Create `rag-mcp` with:

- Python project metadata.
- settings loader.
- core data contracts.
- test directory layout.
- minimal `main.py`.
- script stubs: `ingest.py`, `query.py`, `evaluate.py`, `start_dashboard.py`.

This phase must not modify Java RAG behavior.

### Phase 2: Build Ingestion MVP

Implement:

- file integrity check using SHA256 and SQLite.
- PDF/Markdown loader.
- recursive Markdown-aware splitter.
- chunk record generation with deterministic IDs.
- embedding adapter.
- Chroma upsert.
- BM25 indexer.
- ingestion traces.

Acceptance:

- A sample document can be ingested into a named collection.
- Re-ingesting the same unchanged file skips expensive work.
- The data browser can list documents and chunks.

### Phase 3: Build Query MVP

Implement:

- query processor.
- dense retrieval.
- sparse retrieval.
- RRF fusion.
- optional rerank with fallback.
- citation response builder.
- query traces.

Acceptance:

- `python scripts/query.py --query "..."`
  returns Top-K chunks with citations.
- Query trace includes dense, sparse, fusion, rerank, and final stages.

### Phase 4: Build MCP Server

Implement:

- MCP stdio server.
- `query_knowledge_hub`.
- `list_collections`.
- `get_document_summary`.
- structured content plus Markdown fallback output.

Acceptance:

- A subprocess E2E test can perform `tools/list` and `tools/call`.
- `query_knowledge_hub` returns citations.
- If relevant image files exist, response builder can attach image content.

### Phase 5: Build Dashboard and Evaluation

Implement:

- Streamlit app shell.
- six pages from DEV_SPEC.
- trace service over `logs/traces.jsonl`.
- eval runner and golden test set support.

Acceptance:

- Dashboard starts locally.
- Ingestion/query traces are browsable.
- Evaluation script outputs metrics.

### Phase 6: Java Integration Bridge

Introduce a Java bridge only after the Python subsystem works.

The Java side should stop implementing retrieval logic and delegate to Python
through one of these options:

1. preferred bridge: call the Python MCP tool through a small MCP client adapter.
2. fallback bridge: call a local HTTP wrapper around the Python query engine.

The preferred bridge preserves the DEV_SPEC MCP design. The fallback bridge is
acceptable only if Java MCP client support becomes a blocker.

Current `KnowledgeTools` should become a thin adapter:

```text
KnowledgeTools
  -> PythonRagClient.queryKnowledgeHub(...)
  -> returned cited evidence
  -> RagTrace metadata compatibility adapter for existing UI
```

`RagServiceImpl` should be deprecated after the bridge is live.

### Phase 7: Retire Old Java RAG

Remove or archive:

- Java embedding calls inside `RagServiceImpl`.
- direct pgvector/BM25 retrieval orchestration.
- Java-side RRF and rerank orchestration.
- Java GraphRAG-lite from the main path.

Keep if still useful:

- chat/session/agent/SSE modules.
- React UI.
- old RAG eval data as benchmark input.
- reranker sidecar if reused by Python.

## Error Handling

Ingestion:

- Unchanged file hash returns skipped result.
- Loader failure records failed ingestion status.
- Transform failure degrades per chunk when possible.
- Embedding failure fails the current batch with trace details.
- Upsert failure leaves an error trace and does not mark ingestion success.

Query:

- Dense retrieval failure degrades to sparse results.
- Sparse retrieval failure degrades to dense results.
- Both retrieval routes failing returns a no-evidence result.
- Rerank failure falls back to fused ordering.
- Response building must always include a text fallback.

MCP:

- Invalid arguments return MCP errors with clear messages.
- Logs must never pollute stdout.
- Tool responses must remain parseable even when no evidence is found.

Evaluation:

- Missing optional packages produce explicit skip or import errors.
- Golden set schema errors fail fast.

## Testing Design

Unit tests:

- settings parsing and validation.
- file integrity hash and SQLite records.
- loader output contract.
- splitter chunk IDs and source metadata.
- BM25 index behavior.
- RRF ordering.
- rerank fallback.
- response builder citation formatting.
- trace serialization.

Integration tests:

- ingestion pipeline writes Chroma and BM25 data.
- query engine returns expected chunk IDs.
- MCP server handles tools/list and tools/call.
- dashboard service reads trace JSONL.

E2E tests:

- ingest sample docs.
- query through MCP.
- inspect trace output.
- run evaluation.

Regression tests:

- port existing `rag_eval` data into Python test fixtures.
- compare vector/hybrid/hybrid-rerank metrics.

## Migration Notes for Current Java Assets

Current Java RAG behavior should be treated as reference behavior, not as the
future architecture.

Preserve concepts:

- Hybrid search as default.
- RRF fusion.
- rerank only when needed.
- Self-RAG evidence refusal behavior.
- trace visibility.
- citation markers.

Replace implementation:

- Java `RagServiceImpl` retrieval internals.
- Java PostgreSQL/pgvector as RAG storage.
- Java ingestion inside `DocumentFacadeServiceImpl`.
- Java trace construction as the canonical trace source.

Bridge carefully:

- Keep existing React `RagTrace` shape stable while the Python trace shape
  matures.
- Add a compatibility adapter if Java chat still needs to store trace metadata.
- Do not require React to switch to Streamlit; Streamlit is a management
  dashboard, React remains the product chat UI until a separate decision changes
  it.

## Out of Scope for the First Replacement Pass

- Full cloud deployment.
- Multi-user authentication and authorization.
- Full GraphRAG replacement.
- Full image-to-image retrieval with CLIP.
- Rebuilding the React product UI.
- Removing the Java app before Python parity is proven.
- Tuning every retrieval metric before the framework shape is stable.

## Implementation Defaults

These decisions remove ambiguity for the first implementation plan:

- Java calls Python through MCP stdio when the bridge phase starts. An HTTP
  bridge is only a fallback if MCP client integration from Java becomes a
  concrete blocker.
- The default local embedding adapter is Ollama BGE-M3, because the current Java
  system already uses an Ollama BGE-M3 embedding endpoint. OpenAI-compatible
  embeddings remain a configurable adapter.
- Sparse retrieval uses a separate local BM25 index, not Chroma metadata alone.
  Chroma remains responsible for dense vectors and chunk payloads.
- The existing reranker FastAPI service is reused first through a Python
  adapter. An in-process cross-encoder adapter can replace it later without
  changing the query engine interface.
- Markdown ingestion is first-class in Phase 2 alongside PDF ingestion. This is
  necessary to preserve the current repository workflow and reuse existing
  evaluation material.

## Success Criteria

The replacement is complete when:

- `rag-mcp` is the only canonical RAG implementation.
- MCP `query_knowledge_hub` can answer from indexed documents with citations.
- Ingestion is incremental and observable.
- Query is traceable stage by stage.
- Dashboard can browse data and traces.
- Evaluation can run locally against a golden set.
- Java chat/tool integration delegates to Python RAG.
- Current Java RAG internals are removed, deprecated, or archived.

## Convergence and Cleanup Decision

Date: 2026-07-13

The replacement now moves from version-by-version scaffolding to one gated
convergence plan. The repository keeps this design as the target-state source of
truth and keeps exactly one active implementation plan for unfinished work.
Completed implementation history remains available in Git and in the version
summary in `rag-mcp/README.md`; it does not require one permanent plan document
per increment.

### Delivery Order

Work proceeds in this order, and a phase may start only after the previous
phase's verification gate passes:

1. Remove committed secret defaults and make development configuration safe.
2. Make the Python environment reproducible and connect configuration to real
   embedding and Chroma runtime adapters.
3. Complete one real ingestion-to-answer vertical slice: PDF or Markdown input,
   retrieval, optional rerank, LLM answer generation, and stable citations.
4. Run evaluation through the current pipeline with generated answers instead
   of treating stored observations or reference-answer fallbacks as release
   evidence.
5. Burn in the Python path under the canary profile, enable it in the default
   profile, and then deprecate or remove the Java RAG implementation.
6. Complete dashboard write operations, real trace propagation, MCP resources,
   and multimodal features after the canonical cutover path is stable.

### Repository Cleanup Policy

Cleanup is evidence-based:

- Delete ignored build outputs, caches, logs, and temporary directories when
  they are not needed for an active verification run.
- Delete byte-identical tracked outputs when one canonical copy remains and no
  code references the duplicate.
- Delete unreferenced legacy copies after confirming that Git history or a
  canonical source preserves the information.
- Keep files referenced by dataset builders, tests, migration gates, or runtime
  code until the consuming code is changed and verified.
- Keep Java RAG, evaluation source data, and canary evidence until Python is the
  verified default path.
- Keep compatibility entrypoints such as `AGENTS.md` and `CLAUDE.md` even when
  their contents match, because different agent runtimes discover different
  filenames.
- Keep local Python environments until dependency locking and bootstrap
  instructions are verified; rebuild and remove stale environments only after
  that gate passes.

The active implementation plan must name every tracked file it deletes and the
evidence that makes the deletion safe. Generated-directory cleanup must stay
inside the repository and must not remove user-owned untracked files whose
purpose has not been established.
