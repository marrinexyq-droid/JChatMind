from src.evaluation.ragas_selftest import check_ragas_available


def test_check_ragas_available_returns_status_dict():
    status = check_ragas_available()

    assert "available" in status
    assert "message" in status
