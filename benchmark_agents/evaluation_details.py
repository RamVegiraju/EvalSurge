"""Bound native assessment evidence without exporting raw execution errors or traces."""

import math
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any

from .evaluation_errors import safe_evaluation_error

if TYPE_CHECKING:
    from pandas import DataFrame

REQUEST_TAG = "evalsurge.request_id"
MAX_RATIONALE_CHARACTERS = 2000


def assessment_details(
    frame: "DataFrame | None",
    selected: list[dict[str, Any]],
    scorer: str,
    metric_name: str,
    *,
    catalog: bool,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract one bounded assessment per selected request using exact native tags.

    Args:
        frame: Native MLflow result DataFrame; never joined by prompt or row order.
        selected: Captured request IDs and zero-based case IDs in sampling order.
        scorer: Frozen public criterion identifier.
        metric_name: Exact native assessment name bound to that criterion.
        catalog: Only catalog-owned error codes may receive specific safe guidance.
        run_id: Native evaluation run used to exclude older assessment errors.

    Returns:
        Request/case identity, scalar value, outcome, optional judge rationale, and
        safe error. Only boolean False is a failed quality verdict; other scores
        have no inferred threshold. Non-scalar values are omitted. Rationales are
        protected content, capped at 2,000 characters with explicit truncation.
        Missing/ambiguous correlation never exports another request's reason.

    No tracking-store queries, provider calls, or input mutations are performed.
    Output count is bounded by the frozen per-scorer selection budget (at most 1,000).
    """
    import pandas as pd

    requests = {row["request_id"] for row in selected}
    matched: dict[str, dict[str, Any]] = {}
    duplicates = set()
    for record in frame.to_dict("records") if frame is not None else []:
        tags = record.get("tags")
        request_id = tags.get(REQUEST_TAG) if isinstance(tags, dict) else None
        if not isinstance(request_id, str) or request_id not in requests:
            continue
        if request_id in matched:
            duplicates.add(request_id)
        matched[request_id] = record
    details = []
    for row in selected:
        item = {
            "request_id": row["request_id"],
            "case_id": row.get("case_id"),
            "status": "unavailable",
            "value": None,
            "rationale": None,
            "rationale_truncated": False,
            "error": None,
        }
        record = matched.get(row["request_id"])
        if record is None or row["request_id"] in duplicates:
            code = (
                "assessment_correlation_failed"
                if row["request_id"] in duplicates
                else "assessment_missing"
            )
            item["error"] = safe_evaluation_error(code, scorer).model_dump()
        else:
            raw_error = record.get(f"{metric_name}/error_message")
            has_error, native_code = _native_error(record, metric_name, run_id)
            if has_error or (isinstance(raw_error, str) and raw_error):
                code = native_code if catalog else None
                item.update(status="error", error=safe_evaluation_error(code, scorer).model_dump())
            else:
                value = record.get(f"{metric_name}/value")
                missing = value is None or (pd.api.types.is_scalar(value) and bool(pd.isna(value)))
                if missing:
                    item["error"] = safe_evaluation_error("assessment_missing", scorer).model_dump()
                else:
                    boolean = pd.api.types.is_bool(value)
                    item["status"] = (
                        ("passed" if bool(value) else "failed") if boolean else "scored"
                    )
                    if boolean:
                        item["value"] = bool(value)
                    elif isinstance(value, Integral):
                        item["value"] = int(value)
                    elif isinstance(value, Real) and math.isfinite(value):
                        item["value"] = float(value)
                    elif isinstance(value, str):
                        item["value"] = value[:MAX_RATIONALE_CHARACTERS]
                    rationale = record.get(f"{metric_name}/rationale")
                    if isinstance(rationale, str) and rationale.strip():
                        item["rationale"] = rationale[:MAX_RATIONALE_CHARACTERS]
                        item["rationale_truncated"] = len(rationale) > MAX_RATIONALE_CHARACTERS
        details.append(item)
    return details


def _native_error(
    record: dict[str, Any], metric_name: str, run_id: str | None
) -> tuple[bool, str | None]:
    """Detect matching native errors without reading messages or stack traces.

    Args:
        record: Native result row already correlated to one selected request.
        metric_name: Exact native feedback name.
        run_id: Excludes assessments explicitly linked to other native runs.

    Returns:
        Error presence and code, or None for missing/ambiguous codes. Callers
        allowlist catalog codes and never trust registered error codes.
    """
    assessments = record.get("assessments")
    if not isinstance(assessments, list):
        return False, None
    codes = []
    for assessment in assessments:
        if not isinstance(assessment, dict) or assessment.get("assessment_name") != metric_name:
            continue
        metadata = assessment.get("metadata")
        source_run = (
            metadata.get("mlflow.assessment.sourceRunId") if isinstance(metadata, dict) else None
        )
        if run_id is not None and source_run is not None and source_run != run_id:
            continue
        feedback = assessment.get("feedback")
        error = feedback.get("error") if isinstance(feedback, dict) else None
        if isinstance(error, dict):
            code = error.get("error_code")
            codes.append(code if isinstance(code, str) else None)
    return bool(codes), codes[0] if len(codes) == 1 else None
