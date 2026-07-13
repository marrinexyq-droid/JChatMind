# JChatMind RAG 收敛实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 清理已确认的冗余文件，并按安全、可复现环境、真实 RAG 闭环、真实评估、Canary 切流、管理能力六个阶段，将 `rag-mcp` 收敛为 JChatMind 唯一 canonical RAG 实现。

**架构：** 保留 Java 的聊天、Agent、SSE 与 React 产品界面，把摄取、检索、答案生成、Trace、评估和 MCP 收敛到 Python `rag-mcp`。迁移使用绞杀者模式，每个阶段有独立测试与退出门禁，未通过门禁时不得删除 Java fallback。

**技术栈：** Python 3.11、uv、Pydantic、Chroma、SQLite FTS5、PyMuPDF、Ollama/OpenAI-compatible API、MCP stdio、Java 17、Spring Boot、React 19、pytest、JUnit 5。

## 全局约束

- Python 最低版本保持 `>=3.11`，CI 使用 Python 3.11。
- Java 使用 17，Spring Boot 保持 3.5.8。
- Chroma 是严格环境的 canonical Dense VectorStore；SQLite VectorStore 仅允许开发 fallback。
- 默认真实 Embedding 使用 Ollama BGE-M3；`hash` provider 仅用于显式测试配置。
- Java 优先通过 MCP stdio 调用 Python。
- React 保持产品 UI，Streamlit 只作为管理 Dashboard。
- 任何密钥只能来自环境变量，不允许在 tracked 文件中出现可用默认值。
- 不修改或删除用户的未跟踪 `.github/skills/`。
- `rag-mcp/.venv` 与 `rag-mcp/.deps` 在 Task 3 完成前保留。
- 每个任务独立提交；不得把后续阶段的代码混入前一任务。

---

### Task 1：清理已确认的冗余文件

**文件：**

- Create: `scripts/clean_workspace.ps1`
- Delete: `jchatmind/reranker-service/rag_eval/output/raw_results/results_v1.json`
- Delete: `计划文档/rag_eval/scripts/01_build_ground_truth.py`
- Delete: `计划文档/rag_eval/scripts/03_compute_metrics.py`
- Delete: `计划文档/rag_eval/scripts/04_report.py`
- Delete: `jchatmind_v2/jchatmind_assert/eshop.md`
- Delete: `docs/superpowers/plans/2026-07-03-rag-dev-spec-replacement-1.2.md`
- Delete: `docs/superpowers/plans/2026-07-03-rag-dev-spec-replacement-1.3.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.4.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.5.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.6.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.7.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.8.md`
- Delete: `docs/superpowers/plans/2026-07-04-rag-dev-spec-replacement-1.9.md`
- Delete: `docs/superpowers/plans/2026-07-06-rag-dev-spec-replacement-2.0.md`
- Delete: `docs/superpowers/plans/2026-07-06-rag-dev-spec-replacement-2.1.md`
- Delete: `docs/superpowers/plans/2026-07-06-rag-dev-spec-replacement-2.2.md`
- Delete: `docs/superpowers/plans/2026-07-06-rag-dev-spec-replacement-2.3.md`
- Delete: `docs/superpowers/plans/2026-07-08-rag-dev-spec-replacement-2.4.md`
- Delete: `docs/superpowers/plans/2026-07-08-rag-dev-spec-replacement-2.5.md`
- Delete: `docs/superpowers/plans/2026-07-08-rag-dev-spec-replacement-2.6.md`
- Keep: `docs/superpowers/plans/2026-07-03-rag-dev-spec-replacement-1.0.md`
- Keep: `docs/superpowers/plans/2026-07-03-rag-dev-spec-replacement-1.1.md`
- Keep: `rag-mcp/data/evaluation/ragas_cases.combined.jsonl`

**接口：**

- Consumes: 仓库根路径和一组固定的 ignored 生成目录。
- Produces: `scripts/clean_workspace.ps1 -WhatIf` 和 `scripts/clean_workspace.ps1`，只清理仓库内生成物。

- [ ] **Step 1：再次验证 tracked 删除清单无运行时引用**

Run:

```powershell
rg -n "results_v1\.json|rag-dev-spec-replacement-(1\.[2-9]|2\.[0-6])|jchatmind_v2|计划文档/rag_eval/scripts" . -g '!**/node_modules/**' -g '!**/target/**'
```

Expected：只有文档历史描述；`build_ragas_cases.py` 继续只引用 `1.0/1.1`，并明确不读取 `results_v1.json`。

- [ ] **Step 2：验证精确重复哈希**

Run:

```powershell
Get-FileHash jchatmind/reranker-service/rag_eval/output/raw_results/results.json
Get-FileHash jchatmind/reranker-service/rag_eval/output/raw_results/results_v1.json
```

Expected：两个 SHA256 完全相同。

- [ ] **Step 3：创建安全清理脚本**

```powershell
param([switch]$WhatIf)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$relativeTargets = @(
    "jchatmind/target",
    "ui/dist",
    "rag-mcp/.pytest_cache",
    "rag-mcp/.tmp",
    "rag-mcp/logs",
    "rag-mcp/output",
    "rag-mcp/data/db",
    "scripts/__pycache__"
)

foreach ($relativeTarget in $relativeTargets) {
    $candidate = Join-Path $repoRoot $relativeTarget
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to remove path outside repository: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -WhatIf:$WhatIf
}

$cacheDirs = @(Get-ChildItem -LiteralPath $repoRoot -Directory -Recurse -Filter __pycache__)
$cacheDirs | Sort-Object FullName -Descending |
    ForEach-Object {
        if ($_.FullName.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -WhatIf:$WhatIf
        }
    }
```

- [ ] **Step 4：删除 tracked 冗余文件并运行清理脚本**

使用 `apply_patch` 删除上述 tracked 文件，然后运行：

```powershell
./scripts/clean_workspace.ps1 -WhatIf
./scripts/clean_workspace.ps1
```

Expected：只删除清单中的生成物；`.venv`、`.deps`、评估源数据和 `.github/skills/` 保留。

- [ ] **Step 5：验证清理没有破坏数据集入口**

Run:

```powershell
rg -n "rag-dev-spec-replacement-1\.[01]\.md" rag-mcp/scripts/build_ragas_cases.py
py -3 rag-mcp/scripts/evaluate_ragas_cases.py
git status --short
```

Expected：评估脚本退出码 0；状态只包含本任务计划内的删除和新清理脚本。

- [ ] **Step 6：提交**

```bash
git add scripts/clean_workspace.ps1 docs/superpowers/plans jchatmind/reranker-service/rag_eval/output/raw_results jchatmind_v2 计划文档/rag_eval/scripts
git commit -m "chore: remove superseded rag artifacts"
```

---

### Task 2：删除配置 Secret 默认值并加入本地扫描门禁

**文件：**

- Create: `scripts/check_secrets.py`
- Create: `jchatmind/src/test/java/com/marrine/jchatmind/config/ApplicationConfigurationSecurityTest.java`
- Modify: `jchatmind/src/main/resources/application.yaml`
- Modify: `.github/workflows/rag-canary-acceptance.yml`
- Test: `jchatmind/src/test/java/com/marrine/jchatmind/config/ApplicationConfigurationSecurityTest.java`

**接口：**

- Consumes: tracked 文本文件。
- Produces: `scripts/check_secrets.py`，发现 secret 默认值时退出 1；Spring 配置只读取必填环境变量。

- [ ] **Step 1：写 Java 失败测试**

```java
@Test
void applicationYamlMustNotContainUsableSecretDefaults() throws IOException {
    String yaml = Files.readString(Path.of("src/main/resources/application.yaml"));
    assertThat(yaml).doesNotContain("DB_PASSWORD:");
    assertThat(yaml).doesNotContain("MAIL_PASSWORD:");
    assertThat(yaml).doesNotContain("DEEPSEEK_API_KEY:");
    assertThat(yaml).doesNotContain("ZHIPUAI_API_KEY:");
}
```

- [ ] **Step 2：运行测试确认失败**

Run（从 `jchatmind` 目录执行）：

```powershell
$env:JAVA_HOME='C:\Users\Xyq\.jdks\ms-17.0.19'
./mvnw.cmd -q -Dtest=ApplicationConfigurationSecurityTest test
```

Expected：FAIL，指出当前 YAML 含有 secret 默认值。

- [ ] **Step 3：删除可用默认值**

```yaml
spring:
  datasource:
    password: ${DB_PASSWORD}
  mail:
    password: ${MAIL_PASSWORD}
  ai:
    deepseek:
      api-key: ${DEEPSEEK_API_KEY}
    zhipuai:
      api-key: ${ZHIPUAI_API_KEY}
```

- [ ] **Step 4：增加标准库 Secret 扫描器**

`scripts/check_secrets.py` 扫描 `git ls-files` 输出，至少拒绝以下模式：

```python
FORBIDDEN = (
    re.compile(r"\$\{(?:DB_PASSWORD|MAIL_PASSWORD|DEEPSEEK_API_KEY|ZHIPUAI_API_KEY):[^}]+}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)
```

脚本只输出文件路径和行号，不输出完整 secret。

- [ ] **Step 5：将扫描加入 CI 并验证**

在依赖安装前增加：

```yaml
- name: Check committed secrets
  run: python scripts/check_secrets.py
```

Run:

```powershell
py -3 scripts/check_secrets.py
```

Expected：退出码 0。

- [ ] **Step 6：提交**

```bash
git add scripts/check_secrets.py jchatmind/src/main/resources/application.yaml jchatmind/src/test/java/com/marrine/jchatmind/config/ApplicationConfigurationSecurityTest.java .github/workflows/rag-canary-acceptance.yml
git commit -m "security: remove committed secret defaults"
```

人工门禁：提交完成后必须在对应平台轮换已暴露的邮箱、DeepSeek 和智谱凭证；代码提交不能替代凭证轮换。

Gemini 凭证验证规则：只读取环境变量 `GOOGLE_API_KEY`，使用项目现有 Gemini
adapter 发出一次最小请求，日志只记录 `configured/valid/invalid` 和 HTTP 状态分类，
不得记录 key、Authorization header 或完整响应。DeepSeek、智谱、邮箱和数据库旧
凭证不做可用性探测，统一按已泄露处理并轮换。

---

### Task 3：使用 uv 建立可复现 Python 环境

**文件：**

- Modify: `rag-mcp/pyproject.toml`
- Create: `rag-mcp/uv.lock`
- Create: `rag-mcp/requirements-ci.lock`
- Modify: `rag-mcp/README.md`
- Modify: `.github/workflows/rag-canary-acceptance.yml`

**接口：**

- Consumes: Python 3.11 和 `pyproject.toml`。
- Produces: `uv sync --frozen --all-extras --group dev` 可复现环境；CI 从冻结导出文件安装。

- [ ] **Step 1：把 pytest 移出运行时依赖**

```toml
[project]
dependencies = [
  "pydantic>=2.7",
  "PyYAML>=6.0",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
]
```

- [ ] **Step 2：生成并校验 lock**

Run:

```powershell
cd rag-mcp
uv lock
uv sync --frozen --all-extras --group dev
uv run pytest -q
```

Expected：pytest 可以从新环境启动，且不再依赖 `.deps`。

- [ ] **Step 3：导出 CI 冻结依赖**

Run:

```powershell
uv export --frozen --all-extras --no-dev --output-file requirements-ci.lock
```

Expected：`requirements-ci.lock` 包含哈希或精确版本解析结果，工作区无未预期文件。

- [ ] **Step 4：更新 CI 和 README**

CI 安装命令改为：

```yaml
- name: Install Python dependencies
  run: python -m pip install -r rag-mcp/requirements-ci.lock
```

README 的测试命令改为：

```powershell
uv sync --frozen --all-extras --group dev
uv run pytest -q
```

- [ ] **Step 5：重建本地环境并运行完整验证**

Task 3 通过后，删除旧 `rag-mcp/.venv` 与 `rag-mcp/.deps`，再运行：

```powershell
cd rag-mcp
uv sync --frozen --all-extras --group dev
uv run pytest -q
```

Expected：全量 Python 测试通过。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/pyproject.toml rag-mcp/uv.lock rag-mcp/requirements-ci.lock rag-mcp/README.md .github/workflows/rag-canary-acceptance.yml
git commit -m "build: lock rag-mcp Python environment"
```

---

### Task 4：让 Embedding 配置真正控制运行时

**文件：**

- Create: `rag-mcp/src/libs/embedding_factory.py`
- Create: `rag-mcp/src/libs/ollama_embeddings.py`
- Modify: `rag-mcp/src/libs/embeddings.py`
- Modify: `rag-mcp/src/mcp_server/server.py`
- Modify: `rag-mcp/scripts/ingest.py`
- Modify: `rag-mcp/scripts/query.py`
- Modify: `rag-mcp/scripts/delete_document.py`
- Test: `rag-mcp/tests/libs/test_embedding_factory.py`

**接口：**

- Consumes: `EmbeddingSettings(provider, model, base_url)`。
- Produces: `build_embedding_provider(settings: EmbeddingSettings) -> BaseEmbeddingProvider`。

- [ ] **Step 1：写失败测试**

```python
def test_factory_uses_ollama_settings():
    settings = EmbeddingSettings(
        provider="ollama",
        model="bge-m3",
        base_url="http://localhost:11434",
    )
    provider = build_embedding_provider(settings)
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.model == "bge-m3"
```

- [ ] **Step 2：运行测试确认失败**

Run: `uv run pytest tests/libs/test_embedding_factory.py -q`  
Expected：FAIL，`build_embedding_provider` 尚不存在。

- [ ] **Step 3：实现工厂和 Ollama adapter**

```python
def build_embedding_provider(settings: EmbeddingSettings) -> BaseEmbeddingProvider:
    if settings.provider == "ollama":
        return OllamaEmbeddingProvider(settings.base_url, settings.model)
    if settings.provider == "hash":
        return HashEmbeddingProvider()
    raise ValueError(f"unsupported embedding provider: {settings.provider}")
```

`OllamaEmbeddingProvider.embed_text(text)` 调用 `/api/embed`，读取
`{"embeddings": [[...]]}`，空向量或非 2xx 响应抛出明确异常。

- [ ] **Step 4：替换所有 Hash 硬编码**

`build_local_hub`、`ingest.py`、`query.py` 和 `delete_document.py` 统一调用
`build_embedding_provider(settings.embedding)`。Canary 测试通过显式
`provider: hash` 的临时 settings 保持离线确定性。

- [ ] **Step 5：运行聚焦和完整测试**

```powershell
uv run pytest tests/libs/test_embedding_factory.py tests/integration/test_ingestion_query_flow.py tests/mcp_server/test_server.py -q
uv run pytest -q
```

Expected：全部通过；默认配置不再偷偷使用 HashEmbeddingProvider。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/libs rag-mcp/src/mcp_server/server.py rag-mcp/scripts rag-mcp/tests/libs/test_embedding_factory.py
git commit -m "feat: connect embedding settings to runtime"
```

---

### Task 5：完成 PDF/Markdown 摄取与 Transform seam

**文件：**

- Create: `rag-mcp/src/ingestion/loader_factory.py`
- Create: `rag-mcp/src/ingestion/transforms.py`
- Modify: `rag-mcp/src/ingestion/loaders.py`
- Modify: `rag-mcp/src/ingestion/pipeline.py`
- Modify: `rag-mcp/pyproject.toml`
- Test: `rag-mcp/tests/ingestion/test_pdf_loader.py`
- Test: `rag-mcp/tests/ingestion/test_transforms.py`
- Test: `rag-mcp/tests/integration/test_ingestion_query_flow.py`

**接口：**

- Produces: `load_document(path: Path, collection: str) -> Document`。
- Produces: `Transform.apply(chunk: ChunkRecord) -> ChunkRecord`。
- Produces: `IngestionPipeline.run(..., on_progress: Callable[[str, dict], None] | None = None)`。

- [ ] **Step 1：写 PDF Loader 失败测试**

使用 PyMuPDF 在 `tmp_path` 生成一页 PDF，断言：

```python
document = load_document(pdf_path, "manuals")
assert "JChatMind PDF evidence" in document.text
assert document.metadata["file_suffix"] == ".pdf"
assert document.metadata["page_count"] == 1
```

- [ ] **Step 2：运行测试确认失败**

Run: `uv run pytest tests/ingestion/test_pdf_loader.py -q`  
Expected：FAIL，当前只有 MarkdownLoader。

- [ ] **Step 3：实现 Loader factory 和基础 Transform**

- `.md/.markdown` 使用 `MarkdownLoader`。
- `.pdf` 使用 `PdfLoader`，逐页输出带页码标记的规范 Markdown。
- 其他后缀抛出 `ValueError("unsupported document type: ...")`。
- `RuleCleanupTransform` 规范空白和 BOM。
- `MetadataEnricher` 保留 title、page、source_path 和 sha256。

- [ ] **Step 4：增加 progress 与降级 Trace**

Pipeline 按 `load/split/transform/embed/upsert` 调用 `on_progress`；单个可选
Transform 失败记录 `fallback: true`，Embedding/Upsert 失败则整个 run 失败。

- [ ] **Step 5：运行测试**

```powershell
uv run pytest tests/ingestion tests/integration/test_ingestion_query_flow.py -q
uv run pytest -q
```

Expected：Markdown 行为保持兼容，PDF 可以幂等摄取。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/ingestion rag-mcp/tests/ingestion rag-mcp/tests/integration/test_ingestion_query_flow.py rag-mcp/pyproject.toml rag-mcp/uv.lock rag-mcp/requirements-ci.lock
git commit -m "feat: add PDF ingestion and transform pipeline"
```

---

### Task 6：增加基于证据的 LLM AnswerGenerator

**文件：**

- Create: `rag-mcp/src/libs/llms.py`
- Create: `rag-mcp/src/core/answer_generator.py`
- Modify: `rag-mcp/src/core/settings.py`
- Modify: `rag-mcp/config/settings.yaml`
- Modify: `rag-mcp/src/core/query_engine.py`
- Modify: `rag-mcp/src/mcp_server/tools.py`
- Test: `rag-mcp/tests/core/test_answer_generator.py`
- Test: `rag-mcp/tests/core/test_query_engine.py`

**接口：**

- Produces: `BaseLLMProvider.generate(prompt: str) -> str`。
- Produces: `AnswerGenerator.generate(query: str, evidence: list[RetrievalResult]) -> str`。
- `QueryEngine` 仍返回 `SearchResponse(answer_text, results)`，不破坏 MCP/Java 调用方。

- [ ] **Step 1：写引用约束失败测试**

```python
def test_answer_generator_keeps_citation_markers():
    llm = FakeLLM("RRF combines ranked lists [C1].")
    answer = AnswerGenerator(llm).generate("What is RRF?", [_result("C1")])
    assert answer == "RRF combines ranked lists [C1]."
```

另写一个测试：LLM 输出未知 `[C9]` 时，generator 返回证据 fallback 而不是
发布无效引用。

- [ ] **Step 2：运行测试确认失败**

Run: `uv run pytest tests/core/test_answer_generator.py -q`  
Expected：FAIL，AnswerGenerator 尚不存在。

- [ ] **Step 3：实现 LLM provider 和 AnswerGenerator**

Settings 使用以下稳定字段：

```python
class LlmSettings(BaseModel):
    provider: str = "ollama"
    model: str
    base_url: str
    timeout_seconds: float = 30.0
```

Prompt 必须包含：只能依据 evidence、每个结论带 `[C#]`、无足够证据时明确拒答。
默认 Ollama provider 使用配置的 model/base_url；API key 只从环境变量读取。

- [ ] **Step 4：注入 QueryEngine 并保持 fallback**

有结果且配置 LLM 时生成答案；LLM 超时、无效引用或异常时调用现有
`_build_answer(results)` 返回证据文本，并在 Trace 标记 `fallback: true`。

- [ ] **Step 5：运行测试**

```powershell
uv run pytest tests/core/test_answer_generator.py tests/core/test_query_engine.py tests/mcp_server/test_server.py -q
uv run pytest -q
```

Expected：真实答案与证据 fallback 都保持稳定引用。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/libs/llms.py rag-mcp/src/core rag-mcp/src/mcp_server/tools.py rag-mcp/config/settings.yaml rag-mcp/tests/core
git commit -m "feat: generate cited answers from retrieved evidence"
```

---

### Task 7：让评估运行当前 Pipeline 和 Generated Answers

**文件：**

- Create: `rag-mcp/src/evaluation/pipeline_runner.py`
- Create: `rag-mcp/scripts/evaluate_current_pipeline.py`
- Modify: `rag-mcp/scripts/canary_acceptance.py`
- Modify: `rag-mcp/src/evaluation/ragas_judged.py`
- Test: `rag-mcp/tests/evaluation/test_pipeline_runner.py`
- Test: `rag-mcp/tests/evaluation/test_canary_acceptance.py`

**接口：**

- Produces: `PipelineEvaluationRunner.run(cases, collection) -> PipelineEvaluationReport`。
- Produces: 每个 case 的 `retrieved_context_ids`、`answer`、latency 和 error。

- [ ] **Step 1：写失败测试**

使用 FakeQueryEngine，断言 runner 实际调用每个 case 的 question，并将返回的
chunk ID 和 answer 写入结果；不允许从 `reference_answer` 填充 `answer`。

- [ ] **Step 2：运行测试确认失败**

Run: `uv run pytest tests/evaluation/test_pipeline_runner.py -q`  
Expected：FAIL，runner 尚不存在。

- [ ] **Step 3：实现当前 Pipeline runner**

```python
@dataclass(frozen=True)
class PipelineCaseResult:
    case_id: str
    retrieved_context_ids: list[str]
    answer: str
    latency_ms: float
    error: str | None = None
```

Runner 必须调用当前 QueryEngine，不能读取 legacy observation 作为本轮结果。

- [ ] **Step 4：建立严格 Gate**

Canary acceptance 新增 `--current-pipeline` 和 `--answer-policy generated`；严格模式
发现空 answer、reference fallback、SQLite VectorStore 或 case error 时直接失败。

- [ ] **Step 5：运行评估测试与离线基线**

```powershell
uv run pytest tests/evaluation -q
uv run python scripts/evaluate_ragas_cases.py
uv run python scripts/evaluate_current_pipeline.py --collection rag-canary --output-json output/metrics/current_pipeline.json
```

Expected：静态基线和当前 pipeline 报告分开；发布结论只读取后者。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/evaluation rag-mcp/scripts rag-mcp/tests/evaluation
git commit -m "feat: evaluate the live rag pipeline"
```

---

### Task 8：透传真实 Python Trace 到 Java 和 React

**文件：**

- Modify: `rag-mcp/src/core/query_engine.py`
- Modify: `rag-mcp/src/mcp_server/tools.py`
- Modify: `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/PythonRagMcpClient.java`
- Modify: `jchatmind/src/main/java/com/marrine/jchatmind/model/vo/RagTrace.java`
- Test: `rag-mcp/tests/mcp_server/test_server.py`
- Test: `jchatmind/src/test/java/com/marrine/jchatmind/service/impl/PythonRagMcpClientTest.java`

**接口：**

- MCP structured content 增加 `trace_id` 和 `trace_stages`。
- Java adapter 映射真实 dense/sparse/fusion/rerank/fallback 状态，不再把最终结果
  同时伪装成完整 RRF Trace。

- [ ] **Step 1：写 Python 和 Java 失败测试**

Python 断言 `query_knowledge_hub` structured content 含 trace ID 和阶段数组；Java
断言 `vectorResults`、`bm25Results` 与 `rerankFallback` 来自 structured content。

- [ ] **Step 2：运行聚焦测试确认失败**

```powershell
uv run pytest tests/mcp_server/test_server.py -q
$env:JAVA_HOME='C:\Users\Xyq\.jdks\ms-17.0.19'
./jchatmind/mvnw.cmd -q -f jchatmind/pom.xml -Dtest=PythonRagMcpClientTest test
```

- [ ] **Step 3：扩展 SearchResponse 和 MCP payload**

`SearchResponse` 增加 `trace_id: str | None` 与 `trace_stages: list[dict]`，MCP 只暴露
可序列化且不包含 secret 的阶段信息。

- [ ] **Step 4：更新 Java compatibility adapter**

解析真实阶段；缺少新字段时保留旧版本兼容 fallback，并将 trace 标记为
`partial=true`。

- [ ] **Step 5：运行跨端测试**

Run：Python MCP tests、Java Bridge tests、前端 `npm run lint` 与 `npm run build`。  
Expected：MCP 和 Java 测试通过；前端不需要改变已有 `ragTrace` 消费协议。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/core/query_engine.py rag-mcp/src/mcp_server/tools.py rag-mcp/tests/mcp_server/test_server.py jchatmind/src/main/java/com/marrine/jchatmind jchatmind/src/test/java/com/marrine/jchatmind/service/impl/PythonRagMcpClientTest.java
git commit -m "feat: propagate Python rag trace through Java"
```

---

### Task 8A：修复前端基线质量门禁

**文件：**

- Modify: `ui/src/components/JChatMindLayout.tsx`
- Modify: `ui/src/components/SideMenu.tsx`
- Modify: `ui/src/components/modals/GlassModal.tsx`
- Modify: `ui/src/components/pet/AsteroidPet3D.tsx`
- Modify: `ui/src/components/pet/PetContext.tsx`
- Modify: `ui/src/components/pet/PetOverlay.tsx`
- Modify: `ui/src/contexts/ChatSessionsContext.tsx`
- Modify: `ui/src/hooks/useAgents.tsx`
- Modify: `ui/src/hooks/useKnowledgeBases.tsx`
- Modify: `ui/src/layout/Sidebar.tsx`
- Test: `ui/package.json` 中的 `lint` 与 `build`

**接口：**

- Consumes: 现有 React 组件 props、context 和 hooks。
- Produces: `npm run lint` 0 error、0 warning；`npm run build` 退出码 0，且不改变现有 UI 行为。

- [ ] **Step 1：记录失败基线**

```powershell
cd ui
npm run lint
npm run build
```

Expected：lint 复现当前 `no-explicit-any`、hooks purity、conditional hooks、Fast Refresh
和 effect setState 问题；build 复现或确认本地 native package 安装问题。

- [ ] **Step 2：修复类型与未使用参数**

用现有 domain type、Ant Design event type 或 `unknown` + type guard 替换 `any`；删除
未使用参数，或在确实属于接口契约时从 props 类型与调用方同时移除。

- [ ] **Step 3：修复 React hooks 规则**

- 将随机几何数据移到模块级稳定 seeded generator 或组件外 factory。
- 所有 hooks 移到 early return 之前。
- 补齐 `useMemo` 的 `roughness/metalness` 依赖。
- 将同步 effect 初始化改为 `useState(() => initialValue)`。
- 将 context helper/constants 移到非组件文件，保持 Fast Refresh 边界。

- [ ] **Step 4：重建前端依赖并验证**

若 native package 缺失，使用 lockfile 重建：

```powershell
npm ci
npm run lint
npm run build
```

Expected：lint 0 error、0 warning；build 退出码 0。

- [ ] **Step 5：提交**

```bash
git add ui/src ui/package-lock.json
git commit -m "fix: restore frontend lint and build baseline"
```

---

### Task 9：Canary Burn-in、默认切流与 Java RAG 退役

**文件：**

- Modify: `scripts/rag_cutover_readiness.py`
- Modify: `scripts/verify_rag_canary.py`
- Modify: `jchatmind/src/main/resources/application.yaml`
- Modify: `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java`
- Modify: `jchatmind/src/main/java/com/marrine/jchatmind/service/impl/GraphRagServiceImpl.java`
- Test: `rag-mcp/tests/integration/test_rag_cutover_readiness_script.py`
- Test: `jchatmind/src/test/java/com/marrine/jchatmind/service/impl/PythonBridgeRagServiceTest.java`

**接口：**

- Produces: readiness 报告只有在严格 Chroma、当前 pipeline 评估和默认 Bridge
  条件全部满足时返回 `ready`。

- [ ] **Step 1：扩展 readiness 失败测试**

增加以下 blocker：`current_pipeline_gate_passed`、`default_profile_delegates_to_python`、
`java_rag_internals_retired_or_deprecated`。

- [ ] **Step 2：运行测试确认当前仍 not_ready**

Run:

```powershell
uv run pytest tests/integration/test_rag_cutover_readiness_script.py -q
uv run python ../scripts/rag_cutover_readiness.py --allow-not-ready
```

Expected：当前仓库仍明确列出默认未切流和 Java 未废弃 blocker。

- [ ] **Step 3：执行 Canary Burn-in**

在约定窗口重复运行：

```powershell
uv run python scripts/canary_acceptance.py --require-chroma --current-pipeline --answer-policy generated --ragas-rounds 3
```

记录 Recall@1、MRR、P95 latency、fallback rate 和 error rate。任一指标低于计划阈值
则停止，不修改默认 profile。

固定门禁为：连续 3 轮全部通过；Python Recall@1 与 MRR 相比对应 Java 基线下降均
不超过 `0.02`；error rate 与 fallback rate 均不超过 `1%`；P95 端到端延迟不超过
`8000 ms`。任何 Chroma 降级、空 generated answer 或 readiness error 都直接判失败。

- [ ] **Step 4：默认开启 Python Bridge**

只有 Step 3 通过后，将默认配置改为：

```yaml
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
```

- [ ] **Step 5：先废弃、后删除 Java RAG**

第一提交只增加 `@Deprecated(forRemoval = true)` 和使用告警；后续独立提交在持续
集成稳定后删除 Java 检索编排。聊天、Agent、SSE、React 和兼容 DTO 保留。

- [ ] **Step 6：运行完整门禁并提交**

```powershell
uv run python ../scripts/rag_cutover_readiness.py
uv run python ../scripts/verify_rag_canary.py --acceptance-rounds 3
```

Expected：readiness 为 `ready`，Python、Canary 和 Java Bridge 测试通过。

```bash
git add scripts jchatmind/src/main rag-mcp/tests/integration
git commit -m "feat: make Python rag the default path"
```

---

### Task 10：完成 Dashboard 管理闭环与后续能力

**文件：**

- Modify: `rag-mcp/src/dashboard/app.py`
- Modify: `rag-mcp/src/dashboard/service.py`
- Create: `rag-mcp/src/dashboard/actions.py`
- Test: `rag-mcp/tests/dashboard/test_dashboard_actions.py`
- Test: `rag-mcp/tests/dashboard/test_dashboard_service.py`

**接口：**

- Produces: `DashboardActions.ingest(path, collection)`。
- Produces: `DashboardActions.delete_document(document_id, collection)`。
- Produces: `DashboardActions.run_evaluation(collection)`。

- [ ] **Step 1：写 action 层失败测试**

使用 FakePipeline/FakeVectorStore 验证摄取、删除和评估调用；Dashboard UI 测试不直接
启动真实外部模型。

- [ ] **Step 2：运行测试确认失败**

Run: `uv run pytest tests/dashboard/test_dashboard_actions.py -q`  
Expected：FAIL，DashboardActions 尚不存在。

- [ ] **Step 3：实现 action 层**

Action 层负责调用已有 IngestionPipeline、删除同步和 PipelineEvaluationRunner，UI
只负责输入、进度和结果展示。

- [ ] **Step 4：补齐六页面行为**

- Ingestion Manager：上传、摄取、删除、进度。
- Ingestion/Query Traces：阶段时间线、耗时和 fallback。
- Evaluation Panel：运行当前 pipeline 评估并显示历史趋势。
- Data Browser：文档、Chunk、metadata 和图片引用。

- [ ] **Step 5：运行 Dashboard 与全量门禁**

```powershell
uv run pytest tests/dashboard -q
uv run python scripts/start_dashboard.py --check
uv run pytest -q
```

Expected：Dashboard check 和全量 Python 测试通过。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/dashboard rag-mcp/tests/dashboard
git commit -m "feat: complete rag management dashboard"
```

---

### Task 11：完成 MCP 标准资源与多模态响应

**文件：**

- Create: `rag-mcp/src/mcp_server/resources.py`
- Create: `rag-mcp/src/mcp_server/multimodal.py`
- Modify: `rag-mcp/src/mcp_server/server.py`
- Modify: `rag-mcp/src/mcp_server/tools.py`
- Modify: `rag-mcp/pyproject.toml`
- Test: `rag-mcp/tests/mcp_server/test_resources.py`
- Test: `rag-mcp/tests/mcp_server/test_multimodal.py`
- Test: `rag-mcp/tests/mcp_server/test_server.py`

**接口：**

- Produces: `list_resources() -> list[ResourceDescriptor]`。
- Produces: `read_resource(uri: str) -> ResourceContent`。
- Produces: `assemble_multimodal(citations, image_store) -> list[dict[str, object]]`。

- [ ] **Step 1：写 resources 与图片边界失败测试**

测试 `resources/list` 返回 collection/document URI；`resources/read` 对未知 URI 返回
协议错误；图片文件不存在时只返回 text content；存在受支持图片时返回 MIME 与
base64 content，且不允许读取 `rag-mcp/data/images` 之外的路径。

- [ ] **Step 2：运行测试确认失败**

```powershell
uv run pytest tests/mcp_server/test_resources.py tests/mcp_server/test_multimodal.py -q
```

Expected：FAIL，resources 和 multimodal assembler 尚不存在。

- [ ] **Step 3：实现 Resource contract**

```python
@dataclass(frozen=True)
class ResourceDescriptor:
    uri: str
    name: str
    mime_type: str

@dataclass(frozen=True)
class ResourceContent:
    uri: str
    mime_type: str
    text: str | None = None
    blob: str | None = None
```

URI 只允许 `rag://collections/{collection}` 和
`rag://documents/{collection}/{document_id}` 两种形式。

- [ ] **Step 4：接入 MCP 协议与多模态响应**

Server 增加 `resources/list`、`resources/read`；`query_knowledge_hub` 在引用 metadata
含受控 `image_id` 时追加 image content。所有路径先解析并验证位于配置的图片根目录。

- [ ] **Step 5：运行协议与安全测试**

```powershell
uv run pytest tests/mcp_server -q
uv run pytest -q
```

Expected：旧 `tools/list/tools/call` 保持兼容，resources、多模态和路径越界测试通过。

- [ ] **Step 6：提交**

```bash
git add rag-mcp/src/mcp_server rag-mcp/tests/mcp_server rag-mcp/pyproject.toml rag-mcp/uv.lock rag-mcp/requirements-ci.lock
git commit -m "feat: add MCP resources and multimodal responses"
```

---

## 阶段门禁汇总

| 阶段 | 进入条件 | 退出条件 |
|---|---|---|
| 清理 | 用户批准删除边界 | 无运行时引用、静态评估仍可运行 |
| P0 安全 | 清理提交完成 | Secret 扫描与配置测试通过，凭证已人工轮换 |
| P1 基础 | P0 通过 | `uv sync --frozen` 与全量 Python 测试通过 |
| P2 闭环 | P1 通过 | PDF/Markdown 使用真实 Embedding 返回带引用答案 |
| P3 评估 | P2 通过 | 当前 pipeline + generated answers 严格 gate 通过 |
| P4 切流 | P3 通过 | readiness=`ready`，默认 Bridge 开启，Java RAG 已废弃 |
| P5 管理 | P4 稳定 | Dashboard 六页面形成可操作管理闭环，MCP resources 与多模态测试通过 |

## 最终验证

```powershell
py -3 scripts/check_secrets.py
cd rag-mcp
uv sync --frozen --all-extras --group dev
uv run pytest -q
uv run python scripts/canary_acceptance.py --require-chroma --current-pipeline --answer-policy generated --ragas-rounds 3
cd ../jchatmind
$env:JAVA_HOME='C:\Users\Xyq\.jdks\ms-17.0.19'
./mvnw.cmd -q '-Dtest=!JChatMindV1Test,!JChatMindV2Test' test
cd ../ui
npm run lint
npm run build
cd ..
py -3 scripts/rag_cutover_readiness.py
git status --short
```

完成标准：所有命令退出码为 0；readiness 返回 `ready`；Git 只显示用户已有的
未跟踪 `.github/skills/`，没有生成物或计划外修改。
