from __future__ import annotations

import pytest

from benchmarks.score import score_benchmark


def test_score_benchmark_computes_exact_label_metrics_and_verification_rate() -> None:
    data = {
        "cases": [
            {
                "case_id": "one",
                "gold_issue_ids": ["expected", "missed"],
                "systems": {
                    "prism": {
                        "status": "measured",
                        "predicted_issue_ids": ["expected", "extra"],
                        "verified_prediction_count": 1,
                        "elapsed_seconds": 2.0,
                    }
                },
            }
        ]
    }

    result = score_benchmark(data)[0]

    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 1)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)
    assert result["evidence_verification_rate"] == pytest.approx(0.5)
    assert result["mean_elapsed_seconds"] == 2.0


def test_score_benchmark_omits_unmeasured_systems_without_imputing_zero() -> None:
    result = score_benchmark({"cases": [{"case_id": "one", "gold_issue_ids": ["expected"], "systems": {}}]})
    assert result == []


def test_score_benchmark_rejects_duplicate_predictions() -> None:
    data = {
        "cases": [
            {
                "case_id": "one",
                "gold_issue_ids": [],
                "systems": {"baseline": {"status": "measured", "predicted_issue_ids": ["x", "x"]}},
            }
        ]
    }
    with pytest.raises(ValueError, match="Duplicate predicted issue id"):
        score_benchmark(data)
