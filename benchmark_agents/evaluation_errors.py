"""Map evaluation failures to fixed guidance without leaking provider or scorer content."""

from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from .models import EvaluationError

_DIAGNOSTICS = {
    "judge_authentication_failed": (
        "The judge rejected the configured credentials or permissions.",
        "Check the operator-owned judge profile and model access before submitting another run.",
    ),
    "judge_rate_limited": (
        "The judge provider rate-limited the assessment.",
        "Check provider quotas and wait before retrying explicitly. No model fallback is used.",
    ),
    "judge_timeout": (
        "The judge did not finish within its configured request deadline.",
        "Check provider availability and the frozen judge timeout.",
    ),
    "judge_connection_failed": (
        "The judge provider could not be reached.",
        "Check the runner network and operator-owned judge endpoint configuration.",
    ),
    "judge_provider_error": (
        "The judge provider rejected or failed the assessment.",
        "Check model capabilities and provider health; unsupported parameters are not retried with alternatives.",
    ),
    "invalid_judge_response": (
        "The judge did not return a valid assessment.",
        "Check the scorer output contract and configured model before running load.",
    ),
    "evaluation_backend_error": (
        "The evaluation backend could not complete the assessment.",
        "Check the installed MLflow/scorer compatibility and runner configuration using the run ID.",
    ),
    "assessment_missing": (
        "No request-correlated assessment was available.",
        "Check the scorer output name and MLflow assessment correlation using the recorded run ID.",
    ),
    "assessment_correlation_failed": (
        "Multiple assessment rows claimed the same request.",
        "Check the scorer and MLflow correlation before interpreting individual verdicts.",
    ),
}


def safe_evaluation_error(
    code: str | None, scorer: str | None = None, *, http_status: int | None = None
) -> EvaluationError:
    """Resolve a known code to fixed diagnostics, never echoing an unknown code.

    Args:
        code: Internal failure category or catalog-owned native assessment error code.
        scorer: Frozen criterion identifier, when known.
        http_status: Already-classified provider HTTP status, when available.

    Returns:
        Safe diagnostics; unrecognized codes become a generic backend error.
    """
    if code not in _DIAGNOSTICS:
        code = "evaluation_backend_error"
    message, guidance = _DIAGNOSTICS[code]
    return EvaluationError(
        code=code, message=message, guidance=guidance, scorer=scorer, http_status=http_status
    )


def evaluation_error(error: Exception, scorer: str | None = None) -> EvaluationError:
    """Classify a failure using types/status only, never its message or response body.

    Args:
        error: Provider, verdict-validation, registered-scorer, or native backend failure.
        scorer: Frozen criterion identifier, when known.

    Returns:
        Content-free public diagnostics with fixed operator guidance.
    """
    status = error.status_code if isinstance(error, APIStatusError) else None
    if status in {401, 403}:
        code = "judge_authentication_failed"
    elif status == 429:
        code = "judge_rate_limited"
    elif isinstance(error, (APITimeoutError, TimeoutError)):
        code = "judge_timeout"
    elif isinstance(error, APIConnectionError):
        code = "judge_connection_failed"
    elif isinstance(error, APIStatusError):
        code = "judge_provider_error"
    elif isinstance(error, ValidationError):
        code = "invalid_judge_response"
    else:
        code = "evaluation_backend_error"
    return safe_evaluation_error(code, scorer, http_status=status)
