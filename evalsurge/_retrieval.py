"""Pure typed-receipt consistency checks, without validation-harness dependencies.

This module reads already retrieved SDK metadata. It performs no storage, target,
model, authentication, tracing, or remote calls and exports no protected answers.
Matching terminal receipts establish retrieval parity, not successful inference,
quality, sustainable capacity, or independently verified remote worker cleanup.
"""

from uuid import UUID

from benchmark_agents.v2_models import Report, Result, RunStatus

_TERMINAL = frozenset({"completed", "completed_with_gaps", "failed", "cancelled", "interrupted"})
_PREFLIGHT_CODES = frozenset(
    {
        "authentication_failed",
        "target_http_error",
        "target_timeout",
        "target_connection_error",
        "invalid_stream",
        "invalid_response",
        "worker_failed",
    }
)


def retrieval_evidence(
    run_id: UUID,
    status: RunStatus,
    result: Result,
    report: Report,
    retrieved: Report,
    *,
    remote: bool,
) -> dict[str, bool | str | None]:
    """Compare native typed receipts without traffic or protected-value export.

    Args:
        run_id: SDK-owned run identifier.
        status: Independently retrieved polling metadata.
        result: Independently retrieved typed result.
        report: Report returned by wait or its terminal failure exception.
        retrieved: Independently retrieved report page with identical pagination.
        remote: Whether a service owns work beyond this local client context.

    Returns:
        Identifier, terminal-state/phase and full result/report comparisons, plus
        an allowlisted preflight code. No protected message, answer, reference,
        rationale, destination or credential is copied into the returned mapping.
        Inconsistent/nonterminal remote evidence retains an active-work warning.

    Side Effects:
        None. This inspects existing typed values only; it does not mutate them or
        retrieve, persist, cancel, authenticate, invoke or evaluate any work.
    """
    identities = status.id == result.id == report.run.id == retrieved.run.id == run_id
    outcomes = (status, result, report.run, retrieved.run)
    terminal = all(item.status in _TERMINAL for item in outcomes)
    states = all(item.status == result.status for item in outcomes)
    phases = all(item.phases == result.phases for item in outcomes)
    result_equal = result == report.run == retrieved.run
    report_equal = report == retrieved
    parity = identities and terminal and states and phases and result_equal and report_equal
    code = getattr(report.run.preflight.error, "code", None)
    return {
        "identifiers_agree": identities,
        "terminal_states_and_phases_agree": terminal and states and phases,
        "result_payloads_agree": result_equal,
        "report_pages_agree": report_equal,
        "retrieval_agrees": parity,
        "remote_work_may_remain_active": remote and not parity,
        "preflight_code": code if code in _PREFLIGHT_CODES else None,
    }
