from pathlib import Path

from scripts.evaluate import main


def test_evaluate_script_is_not_dependent_on_current_working_directory(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.chdir(repo_root)

    assert main() == 0
