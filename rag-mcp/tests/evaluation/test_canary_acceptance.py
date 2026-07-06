import json

from scripts.canary_acceptance import main, run_acceptance


def test_run_acceptance_without_smoke_checks_stable_ragas(tmp_path):
    output_json = tmp_path / "acceptance.json"

    report = run_acceptance(
        output_json=output_json,
        run_smoke=False,
        ragas_rounds=2,
    )

    assert report["status"] == "passed"
    assert report["version"] == "2.2"
    assert report["canary"]["skipped"] is True
    assert report["ragas"]["stable"] is True
    assert len(report["ragas"]["rounds"]) == 2
    assert len({row["sha256"] for row in report["ragas"]["rounds"]}) == 1
    assert report["ragas"]["report"]["inventory"]["total_cases"] >= 1000
    assert json.loads(output_json.read_text(encoding="utf-8")) == report


def test_run_acceptance_reports_failed_threshold_without_throwing():
    report = run_acceptance(
        run_smoke=False,
        ragas_rounds=1,
        min_total_cases=999999,
    )

    assert report["status"] == "failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "ragas_total_cases" in failed_gates


def test_run_acceptance_reports_smoke_failure_without_throwing(monkeypatch):
    def fail_smoke(_collection):
        raise AssertionError("smoke failed")

    monkeypatch.setattr("scripts.canary_acceptance._run_smoke_canary", fail_smoke)

    report = run_acceptance(ragas_rounds=1)

    assert report["status"] == "failed"
    assert report["canary"]["error"] == "smoke failed"
    failed_gates = {
        gate["name"]
        for gate in report["gates"]
        if gate["status"] == "failed"
    }
    assert "canary_smoke" in failed_gates


def test_canary_acceptance_cli_writes_json(tmp_path):
    output_json = tmp_path / "cli-acceptance.json"

    exit_code = main(
        [
            "--skip-smoke",
            "--ragas-rounds",
            "2",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["canary"]["skipped"] is True
    assert len(report["ragas"]["rounds"]) == 2
