from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.4"


def evaluate_readiness(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    checks = [
        check_required_files(
            repo_root,
            "python_rag_subsystem_present",
            [
                "rag-mcp/pyproject.toml",
                "rag-mcp/main.py",
                "rag-mcp/src/core/query_engine.py",
                "rag-mcp/src/ingestion/pipeline.py",
                "rag-mcp/src/mcp_server/server.py",
                "rag-mcp/src/observability/trace_context.py",
                "rag-mcp/scripts/ingest.py",
                "rag-mcp/scripts/query.py",
            ],
            "Restore the Python RAG subsystem files before cutover.",
        ),
        check_required_files(
            repo_root,
            "canary_and_ci_gates_present",
            [
                "rag-mcp/scripts/canary_acceptance.py",
                "scripts/verify_rag_canary.py",
                ".github/workflows/rag-canary-acceptance.yml",
            ],
            "Keep the canary acceptance and CI verification gates in place.",
        ),
        check_default_bridge_enabled(repo_root),
        check_canary_profile(repo_root),
        check_java_rag_retired(repo_root),
        check_chroma_canonical(repo_root),
        check_llm_judged_ragas(repo_root),
        check_vision_adapter(repo_root),
    ]
    blockers = [check for check in checks if check["status"] == "blocked"]
    warnings = [check for check in checks if check["status"] == "warning"]
    return {
        "version": VERSION,
        "status": "ready" if not blockers else "not_ready",
        "repo_root": str(repo_root),
        "summary": {
            "passed": sum(1 for check in checks if check["status"] == "passed"),
            "blocked": len(blockers),
            "warnings": len(warnings),
        },
        "blockers": [check["name"] for check in blockers],
        "warnings": [check["name"] for check in warnings],
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Report whether JChatMind RAG is ready for Python default cutover."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate_readiness(args.repo_root)
    if args.output_json is not None:
        output_json = args.output_json if args.output_json.is_absolute() else args.repo_root / args.output_json
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready" or args.allow_not_ready else 1


def check_required_files(
    repo_root: Path,
    name: str,
    relative_paths: list[str],
    next_action: str,
) -> dict[str, Any]:
    missing = [path for path in relative_paths if not (repo_root / path).exists()]
    return check(
        name=name,
        status="passed" if not missing else "blocked",
        evidence={
            "required": relative_paths,
            "missing": missing,
        },
        next_action=next_action,
    )


def check_default_bridge_enabled(repo_root: Path) -> dict[str, Any]:
    application = read_text(repo_root / "jchatmind/src/main/resources/application.yaml")
    python_bridge = yaml_block(application, "python-bridge:")
    expected = [
        "enabled: true",
        "ingestion-enabled: true",
        "readiness-gate-enabled: true",
        "canary-preflight-enabled: true",
        "canary-preflight-fail-on-error: true",
    ]
    missing = [line for line in expected if line not in python_bridge]
    return check(
        name="default_profile_delegates_to_python",
        status="passed" if not missing else "blocked",
        evidence={
            "file": "jchatmind/src/main/resources/application.yaml",
            "missing_enabled_settings": missing,
        },
        next_action=(
            "After canary burn-in, enable the Python bridge, ingestion bridge, "
            "readiness gate, and canary preflight in the default Spring profile."
        ),
    )


def check_canary_profile(repo_root: Path) -> dict[str, Any]:
    canary = read_text(repo_root / "jchatmind/src/main/resources/application-rag-canary.yaml")
    python_bridge = yaml_block(canary, "python-bridge:")
    expected = [
        "enabled: true",
        "ingestion-enabled: true",
        "readiness-gate-enabled: true",
        "canary-preflight-enabled: true",
        "canary-preflight-fail-on-error: true",
    ]
    missing = [line for line in expected if line not in python_bridge]
    profile_present = "on-profile: rag-canary" in canary
    if not profile_present:
        missing.append("on-profile: rag-canary")
    return check(
        name="rag_canary_profile_is_fail_fast",
        status="passed" if not missing else "blocked",
        evidence={
            "file": "jchatmind/src/main/resources/application-rag-canary.yaml",
            "missing_settings": missing,
        },
        next_action="Keep rag-canary as the fail-fast bridge profile before default cutover.",
    )


def check_java_rag_retired(repo_root: Path) -> dict[str, Any]:
    legacy_files = [
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/RagServiceImpl.java",
        "jchatmind/src/main/java/com/marrine/jchatmind/service/impl/GraphRagServiceImpl.java",
    ]
    present = [path for path in legacy_files if (repo_root / path).exists()]
    deprecated_files = [
        path
        for path in present
        if "@Deprecated" in read_text(repo_root / path)
    ]
    deprecated = len(deprecated_files) == len(present)
    status = "passed" if not present or deprecated else "blocked"
    return check(
        name="java_rag_internals_retired_or_deprecated",
        status=status,
        evidence={
            "present_legacy_files": present,
            "deprecated_files": deprecated_files,
            "deprecated_marker_found": deprecated,
        },
        next_action=(
            "Deprecate, archive, or remove Java retrieval internals after the "
            "Python path becomes default and canary metrics stay stable."
        ),
    )


def check_chroma_canonical(repo_root: Path) -> dict[str, Any]:
    pyproject = read_text(repo_root / "rag-mcp/pyproject.toml").lower()
    storage_files = "\n".join(
        read_text(path).lower()
        for path in [
            repo_root / "rag-mcp/src/storage/vector_store.py",
            repo_root / "rag-mcp/src/core/settings.py",
        ]
    )
    has_chroma = "chromadb" in pyproject or "chroma" in storage_files and "sqlite" not in storage_files
    return check(
        name="chroma_is_canonical_vector_store",
        status="passed" if has_chroma else "blocked",
        evidence={
            "pyproject_mentions_chromadb": "chromadb" in pyproject,
            "storage_mentions_sqlite": "sqlite" in storage_files,
        },
        next_action=(
            "Add the Chroma adapter and make it the canonical dense vector store, "
            "or explicitly revise the DEV_SPEC storage decision."
        ),
    )


def check_llm_judged_ragas(repo_root: Path) -> dict[str, Any]:
    scripts_dir = repo_root / "rag-mcp/scripts"
    judged_scripts = list(scripts_dir.glob("*ragas*judg*.py")) if scripts_dir.exists() else []
    readme = read_text(repo_root / "rag-mcp/README.md").lower()
    configured = bool(judged_scripts) and "faithfulness" in readme and "answer relevancy" in readme
    return check(
        name="llm_judged_ragas_gate_configured",
        status="passed" if configured else "blocked",
        evidence={
            "judged_ragas_scripts": [str(path.relative_to(repo_root)) for path in judged_scripts],
            "readme_mentions_faithfulness": "faithfulness" in readme,
            "readme_mentions_answer_relevancy": "answer relevancy" in readme,
        },
        next_action=(
            "Add a judge-model-backed RAGAS gate for faithfulness and answer "
            "relevancy before treating generation quality as production-ready."
        ),
    )


def check_vision_adapter(repo_root: Path) -> dict[str, Any]:
    libs_dir = repo_root / "rag-mcp/src/libs"
    candidate_text = "\n".join(read_text(path) for path in libs_dir.glob("*.py")) if libs_dir.exists() else ""
    has_vision = "BaseVisionLLM" in candidate_text or "Vision" in candidate_text
    return check(
        name="vision_caption_adapter_seam_present",
        status="passed" if has_vision else "warning",
        evidence={
            "libs_dir": "rag-mcp/src/libs",
            "vision_symbol_found": has_vision,
        },
        next_action=(
            "Add the disabled vision caption adapter seam if PDF/image ingestion "
            "is required for the first production cutover."
        ),
    )


def check(name: str, status: str, evidence: dict[str, Any], next_action: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence": evidence,
        "next_action": next_action,
    }


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def yaml_block(text: str, marker: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        base_indent = len(line) - len(line.lstrip())
        block: list[str] = []
        for child in lines[index + 1:]:
            if child.strip() and len(child) - len(child.lstrip()) <= base_indent:
                break
            block.append(child.strip())
        return "\n".join(block)
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
