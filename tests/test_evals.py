"""The eval suite is itself under test: the gates hold on the shipped dataset,
and a fabricated quote in a case would block a release."""

import json
from pathlib import Path

from edlo.evals.run import CASES, HARD_GATES, main, run_case


def test_shipped_dataset_passes_every_gate(tmp_path, capsys):
    assert main("test", reports_dir=tmp_path) == 0
    (report,) = tmp_path.glob("test-*.json")
    data = json.loads(report.read_text())
    assert data["release_blocked"] is False and data["cases"] >= 12
    assert set(HARD_GATES) <= set(data["per_check"])
    assert all(data["per_check"][g]["rate"] == 1.0 for g in HARD_GATES)
    assert {"commit_sha", "dataset_version", "model", "prompt_versions"} <= set(data)
    assert "pass" in capsys.readouterr().out


def test_a_leaked_fabrication_blocks_the_release(tmp_path):
    case = json.loads((CASES / "clean-1.json").read_text())
    case["id"] = "poisoned"
    case["model_cuts"] = [
        {
            "start_ms": 0,
            "end_ms": 5000,
            "exact_quote": "never said in this show",
            "reason": "x",
            "confidence": 1.0,
        }
    ]
    case["expect"] = {
        "kept_model_cuts": 1
    }  # a case that WANTS a fabrication kept is wrong, and the gate says so
    (tmp_path / "cases").mkdir()
    (tmp_path / "cases" / "poisoned.json").write_text(json.dumps(case))
    checks = run_case(case, max_cuts=12, max_cold_opens=5)
    assert (
        checks["grounded_quotes"] is True
    )  # validate dropped it, so nothing leaked...
    assert (
        checks["expected_kept_cuts"] is False
    )  # ...and the case's own expectation is contradicted


def test_every_bucket_is_represented():
    buckets = {json.loads(p.read_text())["bucket"] for p in Path(CASES).glob("*.json")}
    assert buckets == {
        "clean_conversation",
        "messy_speech",
        "sensitive_topic",
        "no_strong_cold_open",
        "adversarial_transcript",
        "human_flags_present",
    }
