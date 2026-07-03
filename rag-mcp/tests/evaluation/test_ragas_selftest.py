from src.evaluation.ragas_selftest import check_ragas_available


def test_check_ragas_available_returns_status_dict():
    status = check_ragas_available()

    assert "available" in status
    assert "message" in status


def test_check_ragas_available_reports_import_failure(monkeypatch):
    def fail_import(name):
        raise RuntimeError(f"{name} dependency failed")

    monkeypatch.setattr("src.evaluation.ragas_selftest.importlib.import_module", fail_import)

    status = check_ragas_available()

    assert status["available"] is False
    assert "dependency failed" in str(status["message"])
