import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "rag_cutover_readiness.py"


def load_readiness_module():
    spec = importlib.util.spec_from_file_location("rag_cutover_readiness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["rag_cutover_readiness"] = module
    spec.loader.exec_module(module)
    return module


def write(root: Path, relative_path: str, text: str = "") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def minimal_repo(root: Path, *, ready: bool) -> Path:
    required_files = [
        "rag-mcp/main.py",
        "rag-mcp/src/core/query_engine.py",
        "rag-mcp/src/ingestion/pipeline.py",
        "rag-mcp/src/mcp_server/server.py",
        "rag-mcp/src/observability/trace_context.py",
        "rag-mcp/scripts/ingest.py",
        "rag-mcp/scripts/query.py",
        "rag-mcp/scripts/canary_acceptance.py",
        "scripts/verify_rag_canary.py",
        ".github/workflows/rag-canary-acceptance.yml",
    ]
    for relative_path in required_files:
        write(root, relative_path)
    write(
        root,
        "jchatmind/src/main/resources/application-rag-canary.yaml",
        """
spring:
  config:
    activate:
      on-profile: rag-canary
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
""",
    )
    if ready:
        write(
            root,
            "jchatmind/src/main/resources/application.yaml",
            """
rag:
  python-bridge:
    enabled: true
    ingestion-enabled: true
    readiness-gate-enabled: true
    canary-preflight-enabled: true
    canary-preflight-fail-on-error: true
""",
        )
        write(root, "rag-mcp/pyproject.toml", 'dependencies = ["chromadb>=0.5", "ragas==0.4.3"]')
        write(root, "rag-mcp/src/storage/vector_store.py", "class ChromaVectorStore: pass")
        write(root, "rag-mcp/src/core/settings.py", "chroma_path = 'data/db/chroma'")
        write(root, "rag-mcp/scripts/evaluate_ragas_judged.py")
        write(root, "rag-mcp/src/libs/vision.py", "class BaseVisionLLM: pass")
        write(root, "rag-mcp/README.md", "faithfulness and answer relevancy")
    else:
        write(
            root,
            "jchatmind/src/main/resources/application.yaml",
            """
rag:
  python-bridge:
    enabled: false
    ingestion-enabled: false
    readiness-gate-enabled: false
    canary-preflight-enabled: false
    canary-preflight-fail-on-error: false
  self-rag:
    enabled: true
""",
        )
        write(root, "rag-mcp/pyproject.toml", 'dependencies = ["pytest>=8"]')
        write(root, "rag-mcp/src/storage/vector_store.py", "class SqliteVectorStore: pass")
        write(root, "rag-mcp/src/core/settings.py", "vector_store_db = 'data/db/vector_store.db'")
        write(root, "rag-mcp/README.md", "faithfulness requires a judge")
        write(root, "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java")
    return root


def test_not_ready_repo_reports_concrete_blockers(tmp_path):
    module = load_readiness_module()

    report = module.evaluate_readiness(minimal_repo(tmp_path, ready=False))

    assert report["status"] == "not_ready"
    assert "default_profile_delegates_to_python" in report["blockers"]
    default_bridge = next(
        check
        for check in report["checks"]
        if check["name"] == "default_profile_delegates_to_python"
    )
    assert "enabled: true" in default_bridge["evidence"]["missing_enabled_settings"]
    assert "java_rag_internals_retired_or_deprecated" in report["blockers"]
    assert "chroma_is_canonical_vector_store" in report["blockers"]
    assert "vision_caption_adapter_seam_present" in report["warnings"]


def test_ready_repo_passes_cutover_gate(tmp_path):
    module = load_readiness_module()

    report = module.evaluate_readiness(minimal_repo(tmp_path, ready=True))

    assert report["status"] == "ready"
    assert report["blockers"] == []
    assert report["summary"]["warnings"] == 0


def test_cli_returns_nonzero_unless_allow_not_ready(tmp_path):
    minimal_repo(tmp_path, ready=False)

    blocked = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    allowed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
            "--allow-not-ready",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert blocked.returncode == 1
    assert allowed.returncode == 0
    assert '"status": "not_ready"' in allowed.stdout
