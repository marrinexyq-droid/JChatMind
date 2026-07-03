import subprocess
import sys

from pathlib import Path


def test_ingest_and_query_scripts_work_from_repo_root(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    source = tmp_path / "cli.md"
    source.write_text("# CLI RAG\n\nThe command line path supports hybrid retrieval.", encoding="utf-8")

    ingest = subprocess.run(
        [
            sys.executable,
            str(repo_root / "rag-mcp/scripts/ingest.py"),
            str(source),
            "--collection",
            "cli-test",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ingest.returncode == 0
    assert "status=ingested" in ingest.stdout or "status=skipped" in ingest.stdout

    query = subprocess.run(
        [
            sys.executable,
            str(repo_root / "rag-mcp/scripts/query.py"),
            "hybrid retrieval",
            "--collection",
            "cli-test",
            "--top-k",
            "1",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert query.returncode == 0
    assert "Evidence found:" in query.stdout
