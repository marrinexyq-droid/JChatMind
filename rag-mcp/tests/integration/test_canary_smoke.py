import json
import subprocess
import sys
from pathlib import Path

from scripts.canary_smoke import run_canary


def test_run_canary_uses_isolated_project_root(tmp_path):
    report = run_canary(tmp_path, collection="canary-test")

    assert report["status"] == "passed"
    assert report["collection"] == "canary-test"
    assert report["chunk_count"] >= 1
    assert report["mcp"]["status"]["status"] == "ready"
    assert "query_knowledge_hub" in report["mcp"]["tools"]
    assert report["query"]["result_count"] >= 1
    assert report["summary"]["chunk_count"] >= 1
    assert report["traces"]["ingestion"] >= 1
    assert report["traces"]["query"] >= 1
    assert (tmp_path / "data/db/vector_store.db").exists()
    assert (tmp_path / "logs/traces.jsonl").exists()


def test_canary_smoke_cli_outputs_json_report(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    workdir = tmp_path / "canary-root"

    process = subprocess.run(
        [
            sys.executable,
            str(repo_root / "rag-mcp/scripts/canary_smoke.py"),
            "--workdir",
            str(workdir),
            "--collection",
            "canary-cli",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["status"] == "passed"
    assert report["collection"] == "canary-cli"
    assert report["mcp"]["server_version"] == "2.0.0"
    assert report["query"]["citation_ids"][0] == "C1"
