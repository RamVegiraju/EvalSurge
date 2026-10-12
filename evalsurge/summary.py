"""Content-free summaries shared by Python, notebooks and the CLI.

This presentation module performs no execution, I/O, credential resolution or
inference. It projects only approved state vocabulary, numeric observations and
bounded public scorer identifiers; protected report evidence stays in the DTO.
"""

import math
import re
from collections.abc import Mapping
from typing import Any

from benchmark_agents.v2_models import Report, Result

_LIFECYCLE_STATES = {
    "queued",
    "planning",
    "preflighting",
    "running",
    "profiling",
    "evaluating",
    "completed",
    "completed_with_gaps",
    "failed",
    "interrupted",
    "cancelled",
}
_PHASE_STATES = _LIFECYCLE_STATES | {
    "pending",
    "not_run",
    "passed",
    "skipped",
    "completed_with_errors",
    "no_ready_scorers",
    "needs_configuration",
    "configuration_changed",
}
_EVIDENCE_GAPS = {
    "incomplete_measurements",
    "evaluation_unavailable",
    "planning_failed",
    "internal_trace_coverage",
    "profiling_failed",
    "generator_health_unavailable",
    "generator_degraded",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    """Ignore malformed legacy objects rather than rendering their representation."""
    return value if isinstance(value, Mapping) else {}


def _number(value: Any, *, percentage: bool = False) -> str:
    """Format finite observations; missing, boolean and nonfinite values stay unknown."""
    try:
        finite = type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        return "unavailable"
    if percentage:
        scaled = value * 100
        try:
            finite_scaled = math.isfinite(scaled)
        except OverflowError:
            finite_scaled = False
        if not finite_scaled:
            return "unavailable"
        return f"{scaled:.1f}%"
    return f"{value:.2f}"


def _state(value: Any, allowed: set[str]) -> str:
    """Never emit arbitrary labels, control characters or provider diagnostics."""
    return value if isinstance(value, str) and value in allowed else "unknown"


def _generator_lines(metrics: Mapping[str, Any]) -> list[str]:
    """Project separate overlapping waits without certifying generator health."""
    health = metrics.get("generator_health")
    if not isinstance(health, Mapping):
        return ["Generator health: unavailable (historical or missing telemetry)."]
    state = _state(health.get("status"), {"unknown", "degraded"})
    lag = _mapping(health.get("hub_lag"))
    lines = [
        f"Generator health: {state}; no calibrated healthy-runner threshold.",
        f"Hub wake-up lag: mean {_number(lag.get('mean_ms'))} ms, "
        f"max {_number(lag.get('max_ms'))} ms, {_number(lag.get('count'))} observations.",
        "Journal observations (ms)         mean          max",
    ]
    journal = _mapping(health.get("journal"))
    for key, label in (
        ("enqueue_wait_ms", "Queue admission wait"),
        ("durable_wait_ms", "Durable acknowledgment wait"),
        ("write_and_fsync_ms", "Native write + fsync"),
    ):
        timing = _mapping(journal.get(key))
        lines.append(
            f"{label:<28} {_number(timing.get('mean_ms')):>12} {_number(timing.get('max_ms')):>12}"
        )
    drained = journal.get("drained")
    drain = "yes" if drained is True else "no" if drained is False else "unknown"
    lines.append(
        f"Journal drained: {drain}; failures {_number(journal.get('writer_failures'))}; "
        f"backpressure events {_number(journal.get('backpressure_events'))}."
    )
    backpressure = journal.get("backpressure_events")
    if type(backpressure) is int and backpressure > 0:
        lines.append(
            "Journal backpressure observed: achieved throughput may be generator-limited; "
            "do not interpret it as target capacity."
        )
    lines.append(
        "Journal waits overlap; do not add them to latency or subtract them as a baseline. "
        "Durable waits can reduce throughput even without queue backpressure. "
        "CPU, memory, transport and server-only timing are not measured."
    )
    return lines


def format_summary(value: Result | Report | Mapping[str, Any]) -> str:
    """Render one content-free summary without executing or modifying the run.

    Args:
        value: Typed v2 result/report, or a legacy result/report dictionary. The
            result belongs to the caller; only presentation fields are projected.
            Invalid legacy states and labels become unknown, not raw output.

    Returns:
        Plain text suitable for ``print(format_summary(result))`` in Python,
        notebooks or terminals, with no trailing newline. Latency/TTFT are
        successful client observations in milliseconds. Rates include drain;
        missing observations remain unavailable, while known zero remains zero.
        Completion, quality, evidence coverage and generator limitations remain
        independent. Scorer summaries are bounded to the ten-requested-criteria
        contract; arbitrary error text, prompts, answers, paths and URLs are omitted.

    Raises:
        TypeError: The input is neither a v2 result/report nor a mapping.

    Side effects:
        None. This performs no network, file, model or credential access, does
        not change exit codes and does not certify accuracy or target capacity.
    """
    if isinstance(value, Report):
        value = value.run
    if isinstance(value, Result):
        # Do not serialize the report's request evidence, rationales or preflight.
        run = {
            "status": value.status,
            "phases": value.phases.model_dump(mode="json"),
            "summary": value.summary.model_dump(mode="json"),
            "evidence": value.evidence.model_dump(mode="json"),
            "metrics": value.metrics.model_dump(mode="json") if value.metrics else None,
            "evaluation": {
                "omitted_criteria": max(0, len(value.evaluation.results) - 10),
                "request_coverage": value.evaluation.request_coverage.model_dump(mode="json")
                if value.evaluation.request_coverage
                else None,
                "results": [
                    {
                        "scorer": outcome.scorer,
                        "status": outcome.status,
                        "coverage": {"selected": outcome.coverage.selected}
                        if outcome.coverage
                        else None,
                        "attempted": outcome.attempted,
                        "scored": outcome.scored,
                        "judge_errors": outcome.judge_errors,
                        "pass_rate": outcome.pass_rate,
                    }
                    for outcome in value.evaluation.results[:10]
                ],
            },
        }
    elif isinstance(value, Mapping):
        run = _mapping(value.get("run")) if "run" in value else value
    else:
        raise TypeError("Summary requires a v2 Result, Report or result/report mapping.")
    lines = []
    if "status" in run:
        lines.append(f"Lifecycle: {_state(run.get('status'), _LIFECYCLE_STATES)}.")
    phases = _mapping(run.get("phases"))
    if phases:
        for key, label in (
            ("planning", "Planning"),
            ("inference", "Inference readiness"),
            ("evaluation_readiness", "Judge readiness"),
            ("load", "Load"),
            ("profiling", "Profiling"),
            ("evaluation", "Evaluation"),
        ):
            lines.append(f"{label}: {_state(phases.get(key), _PHASE_STATES)}.")
    decisions = _mapping(run.get("summary"))
    for key, label, allowed in (
        ("performance", "Performance", {"pending", "complete", "incomplete", "not_run"}),
        ("quality", "Quality evidence", {"pending", "off", "available", "unavailable"}),
    ):
        if key in decisions:
            lines.append(f"{label}: {_state(decisions.get(key), allowed)}.")
    gaps = decisions.get("evidence_gaps")
    if isinstance(gaps, (list, tuple)):
        safe_gaps = sorted({gap for gap in gaps if isinstance(gap, str) and gap in _EVIDENCE_GAPS})
        if safe_gaps:
            lines.append("Evidence gaps: " + ", ".join(safe_gaps) + ".")
    evidence = _mapping(run.get("evidence"))
    if evidence:
        lines.append("Evidence capability             configured      observed state")
        for key, label in (
            ("load_measurements", "Load measurements"),
            ("answer_evaluation", "Captured-answer judging"),
            ("internal_profiling", "Internal profiling"),
            ("trace_aware_evaluation", "Trace-aware judging"),
        ):
            entry = _mapping(evidence.get(key))
            configured = entry.get("configured")
            selection = "yes" if configured is True else "no" if configured is False else "unknown"
            state = _state(entry.get("state"), {"pending", "observed", "unavailable", "off"})
            lines.append(f"{label:<28} {selection:>12} {state:>19}")
        lines.append("Configured is not verified; observed evidence is not a quality pass.")
    metrics = run.get("metrics")
    if not isinstance(metrics, Mapping):
        lines.append("Performance metrics: unavailable.")
    else:
        lines.append(
            f"Attempts: {_number(metrics.get('requests'))}; "
            f"successful: {_number(metrics.get('successful_requests'))}."
        )
        lines.append("Successful observations (ms)       p50          p95          p99")
        timings = _mapping(metrics.get("timing_successful_only"))
        for key, label in (("latency_ms", "Latency"), ("ttft_ms", "Answer-text TTFT")):
            timing = _mapping(timings.get(key))
            lines.append(
                f"{label:<28}"
                + " ".join(f"{_number(timing.get(p)):>12}" for p in ("p50", "p95", "p99"))
            )
            lines.append(
                f"  Coverage: {_number(timing.get('count'))} successful observations / "
                f"{_number(metrics.get('requests'))} total attempts."
            )
        lines.extend(
            [
                "Failed and timed-out attempts are excluded from these percentiles; "
                "inspect the error rate and retained attempt records alongside them.",
                f"Successful throughput: {_number(metrics.get('successful_tps'))} requests/s.",
                f"Completed throughput: {_number(metrics.get('completed_tps'))} requests/s.",
                f"Error rate: {_number(metrics.get('error_rate'), percentage=True)}.",
                f"Token-usage coverage: {_number(metrics.get('token_usage_coverage'), percentage=True)}.",
                "Reported output tokens: "
                f"{_number(metrics.get('reported_output_tokens_per_second'))} tokens/s.",
                "Measurements: "
                f"{'complete' if metrics.get('measurement_complete') is True else 'incomplete'}.",
                "Throughput includes drain; this single load level does not establish sustainable capacity.",
            ]
        )
        lines.extend(_generator_lines(metrics))
    evaluation = _mapping(run.get("evaluation"))
    coverage = _mapping(evaluation.get("request_coverage"))
    if coverage:
        lines.append(
            f"Evaluation input coverage: {_number(coverage.get('successful'))} successful / "
            f"{_number(coverage.get('total'))} total attempts; "
            f"{_number(coverage.get('failed'))} failed attempts excluded from judging."
        )
    judges = evaluation.get("results")
    if isinstance(judges, (list, tuple)) and judges:
        lines.append(
            "Judge                         selected  attempted     scored     errors    pass rate"
        )
        for judge in judges[:10]:
            if not isinstance(judge, Mapping):
                continue
            name = judge.get("scorer")
            if not isinstance(name, str) or not re.fullmatch(
                r"(?:registered:)?[a-zA-Z0-9_-]{1,75}", name
            ):
                name = "<unknown>"
            coverage = _mapping(judge.get("coverage"))
            lines.append(
                f"{name:<28} {_number(coverage.get('selected')):>10} "
                f"{_number(judge.get('attempted')):>10} {_number(judge.get('scored')):>10} "
                f"{_number(judge.get('judge_errors')):>10} "
                f"{_number(judge.get('pass_rate'), percentage=True):>12}"
            )
            state = _state(
                judge.get("status"),
                {
                    "completed",
                    "partial",
                    "failed",
                    "configuration_changed",
                    "needs_configuration",
                    "no_eligible_outputs",
                },
            )
            lines.append(f"  Judge execution: {state}.")
        lines.append(
            "Judge completion is separate from quality passing; no CI threshold is applied."
        )
        if len(judges) > 10 or evaluation.get("omitted_criteria", 0):
            lines.append("Additional criteria omitted; inspect the typed report for full coverage.")
    return "\n".join(lines)
