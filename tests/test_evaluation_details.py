"""Verify bounded, request-correlated quality evidence and safe execution diagnostics."""

import json

import numpy as np
import pandas as pd
import pytest

from benchmark_agents.evaluation_details import assessment_details


def captured(request_id: str, case_id: int = 0) -> dict:
    return {"request_id": request_id, "case_id": case_id}


def record(request_id: str, value, rationale=None, **extra) -> dict:
    return {
        "tags": {"evalsurge.request_id": request_id},
        "correctness/value": value,
        "correctness/rationale": rationale,
        **extra,
    }


def details(records: list[dict], selected: list[dict], *, catalog=True) -> list[dict]:
    return assessment_details(
        pd.DataFrame(records), selected, "correctness", "correctness", catalog=catalog
    )


def test_reordered_assessments_match_request_ids_not_dataframe_order():
    result = details(
        [record("second", False, "Missed the deadline."), record("first", True, "Accurate.")],
        [captured("first"), captured("second", 3)],
    )
    assert [item["request_id"] for item in result] == ["first", "second"]
    assert [item["status"] for item in result] == ["passed", "failed"]
    assert result[1]["case_id"] == 3
    assert result[1]["rationale"] == "Missed the deadline."
    assert result[1]["value"] is False
    assert result[1]["error"] is None


@pytest.mark.parametrize("value", [0, 0.25, "no", "failed", [False], {"score": 0}])
def test_nonboolean_scores_do_not_invent_a_quality_threshold(value):
    result = details([record("first", value)], [captured("first")])
    assert result[0]["status"] == "scored"


def test_missing_rationale_is_explicit_and_numpy_values_are_json_safe():
    result = details(
        [record("first", np.bool_(False), np.nan), record("second", np.float64(0.5))],
        [captured("first"), captured("second")],
    )
    assert result[0]["status"] == "failed"
    assert result[0]["rationale"] is None
    assert result[1]["value"] == 0.5
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("records", [[], [record("unknown", False, "Wrong answer.")]])
def test_missing_or_unmatched_rows_never_fabricate_failure_reasons(records):
    result = details(records, [captured("first")])
    assert result[0]["status"] == "unavailable"
    assert result[0]["rationale"] is None
    assert result[0]["error"]["code"] == "assessment_missing"


def test_duplicate_correlation_is_rejected_instead_of_choosing_a_reason():
    result = details(
        [record("first", False, "First reason."), record("first", True, "Second reason.")],
        [captured("first")],
    )
    assert result[0]["status"] == "unavailable"
    assert result[0]["error"]["code"] == "assessment_correlation_failed"
    assert "reason" not in json.dumps(result).lower()


@pytest.mark.parametrize("catalog", [True, False])
def test_execution_errors_do_not_expose_raw_error_messages_or_rationales(catalog):
    result = details(
        [
            record(
                "first",
                np.nan,
                "secret-provider-body",
                **{
                    "correctness/error_message": "secret-provider-body",
                    "assessments": [
                        {
                            "assessment_name": "correctness",
                            "feedback": {
                                "error": {
                                    "error_code": "judge_rate_limited",
                                    "error_message": "secret-provider-body",
                                }
                            },
                        }
                    ],
                },
            )
        ],
        [captured("first")],
        catalog=catalog,
    )
    assert result[0]["status"] == "error"
    assert result[0]["rationale"] is None
    assert result[0]["error"]["code"] == (
        "judge_rate_limited" if catalog else "evaluation_backend_error"
    )
    assert result[0]["error"]["guidance"]
    assert "secret-provider-body" not in json.dumps(result)


def test_missing_nan_value_and_rationale_length_are_bounded():
    result = details(
        [record("first", float("nan")), record("second", False, "a" * 2500)],
        [captured("first"), captured("second")],
    )
    assert result[0]["status"] == "unavailable"
    assert result[1]["rationale"] == "a" * 2000
    assert result[1]["rationale_truncated"] is True
    json.dumps(result, allow_nan=False)


def test_unselected_results_and_contents_are_not_exported():
    result = details(
        [record("first", False, "Policy mismatch."), record("unknown", False, "private")],
        [captured("first")],
    )
    assert len(result) == 1
    assert "private" not in json.dumps(result)
    assert "tags" not in result[0]


def test_native_error_without_a_message_never_exports_its_rationale():
    result = details(
        [
            record(
                "first",
                False,
                "secret-provider-body",
                assessments=[
                    {
                        "assessment_name": "correctness",
                        "feedback": {
                            "error": {"error_code": "unknown-secret", "error_message": ""}
                        },
                    }
                ],
            )
        ],
        [captured("first")],
    )
    assert result[0]["status"] == "error"
    assert result[0]["error"]["code"] == "evaluation_backend_error"
    assert "secret" not in json.dumps(result)


def test_errors_from_a_different_native_run_do_not_override_a_quality_verdict():
    frame = pd.DataFrame(
        [
            record(
                "first",
                False,
                "Actual quality reason.",
                assessments=[
                    {
                        "assessment_name": "correctness",
                        "metadata": {"mlflow.assessment.sourceRunId": "old-run"},
                        "feedback": {"error": {"error_code": "judge_timeout"}},
                    }
                ],
            )
        ]
    )
    result = assessment_details(
        frame,
        [captured("first")],
        "correctness",
        "correctness",
        catalog=True,
        run_id="current-run",
    )
    assert result[0]["status"] == "failed"
    assert result[0]["rationale"] == "Actual quality reason."
