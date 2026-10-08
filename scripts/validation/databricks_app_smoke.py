"""Prepare or run a consent-gated, performance-only smoke check of one deployed App.

Dry-run is the default and does not resolve profiles, read credentials, discover
Apps, create artifacts, or send traffic. A live run requires --live together with
--accept-paid-traffic, an exact selected profile/App, a safe prompt, and a dedicated
artifact directory. It performs one excluded inference probe and at most 500
measured invocations through the existing Locust engine. There are no planner or
judge calls, retries, deployment changes, background jobs, or resumed invocations.

These are top-level invocation bounds, not a monetary or agent tool-call quota.
The App operator must constrain its internal model/tool spend and actions first,
including DurableAgentServer recovery that can execute a handler more than once.
SDK discovery/authentication has nominal transport budgets, not hard wall-clock
termination. This smoke check does not establish capacity or calibrated quality.
"""

import argparse
import json
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Validate explicit selections and small finite bounds without any external I/O.

    Args:
        arguments: CLI arguments; None uses the process arguments.

    Returns:
        Validated operator selections, a synthetic prompt, and consent flags.

    Raises:
        SystemExit: Selections, bounds, or live consent are missing or invalid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Exact user-selected OAuth profile.")
    parser.add_argument("--app-name", required=True, help="Existing authorized App resource.")
    parser.add_argument("--prompt", required=True, help="Short synthetic, non-sensitive prompt.")
    parser.add_argument(
        "--protocol",
        choices=("databricks-agent-runtime", "mlflow-agent-server"),
        default="databricks-agent-runtime",
        help="Current DurableAgentServer default; explicitly select legacy MLflow for /responses.",
    )
    parser.add_argument(
        "--max-requests", type=int, default=2, help="Measured cap 1..500; probe adds one."
    )
    parser.add_argument(
        "--concurrency", type=int, default=1, help="Closed-loop Locust users, 1..5."
    )
    parser.add_argument("--duration", type=float, default=10, help="Dispatch seconds, 0.1..180.")
    parser.add_argument("--timeout", type=float, default=30, help="Per-attempt seconds, 0.1..60.")
    parser.add_argument(
        "--artifact-dir", type=Path, help="Dedicated protected local evidence directory."
    )
    parser.add_argument("--live", action="store_true", help="Resolve the App and invoke it.")
    parser.add_argument(
        "--accept-paid-traffic",
        action="store_true",
        help="Consent to the probe + measured calls, model/tool spend and target side effects.",
    )
    options = parser.parse_args(arguments)
    if not options.profile.strip() or len(options.profile) > 512:
        parser.error("--profile must name one explicitly selected profile")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", options.app_name):
        parser.error("--app-name must be a valid existing App resource name")
    if not options.prompt.strip() or len(options.prompt) > 1000:
        parser.error("--prompt must be a nonempty synthetic prompt of at most 1000 characters")
    if not 1 <= options.max_requests <= 500:
        parser.error("--max-requests must be 1..500, plus one excluded probe")
    if not 1 <= options.concurrency <= 5:
        parser.error("--concurrency must be 1..5")
    for name, maximum in (("duration", 180), ("timeout", 60)):
        value = getattr(options, name)
        if not math.isfinite(value) or not 0.1 <= value <= maximum:
            parser.error(f"--{name} must be finite and between 0.1 and {maximum} seconds")
    if options.live and (not options.accept_paid_traffic or options.artifact_dir is None):
        parser.error("--live requires --accept-paid-traffic and --artifact-dir")
    return options


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Return content-free execution limits; private selections/prompts are excluded."""
    return {
        "live": options.live,
        "protocol": options.protocol,
        "concurrency": options.concurrency,
        "excluded_inference_probes": 1,
        "max_measured_invocations": options.max_requests,
        "max_total_invocations": options.max_requests + 1,
        "server_recovery_attempts_bounded": False,
        "dispatch_seconds": options.duration,
        "per_attempt_timeout_seconds": options.timeout,
        "wait_timeout_seconds": max(300.0, options.duration + 2 * options.timeout + 60),
        "evaluation_mode": "off",
        "tracing_enabled": False,
        "monetary_quota_enforced": False,
        "sustainable_capacity_established": False,
    }


def execute(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Run one authorized App check using operator resolution and the public local API.

    Args:
        options: Live-consented options with exact profile/App and a dedicated store.

    Returns:
        Exit code and a content-free validation record. Zero requires passed probe,
        completed load, and no measured failures; it is not a quality verdict.

    Raises:
        ValueError: Live consent is absent; no discovery or traffic then occurs.
        Exception: Resolution, local ownership, or execution fails before a report.
            main suppresses raw exception messages to keep private values out of logs.

    Side Effects:
        OAuth/App discovery, one probe, and bounded measured target traffic can incur
        spend or execute tools. Owns/drains one local coordinator. Persists protected
        captures and a content-free validation.json in the selected directory.
        Never mutates process environment or deploys resources. No target retry occurs.
    """
    if not options.live or not options.accept_paid_traffic or options.artifact_dir is None:
        raise ValueError("Live validation requires explicit consent and a dedicated store")
    if options.artifact_dir.exists() and any(options.artifact_dir.iterdir()):
        raise ValueError(
            "Use a new or empty dedicated artifact directory; no previous record is overwritten"
        )
    from benchmark_agents.configuration import configured_environment
    from benchmark_agents.settings import ConnectionSettings, Settings
    from benchmark_agents.storage import atomic_json
    from benchmark_agents.target_resolver import resolve_registered_target
    from evalsurge import Agent, EvalSurge, Load, RunFailed, Sample

    settings = Settings(
        artifact_dir=options.artifact_dir,
        connections={
            "sample": ConnectionSettings(
                kind="databricks-app",
                app_name=options.app_name,
                profile=options.profile,
                protocols=(options.protocol,),
            )
        },
    )
    with configured_environment(settings.to_environment()):
        target, connection = resolve_registered_target("sample", settings.connections)
        with EvalSurge.local(artifact_dir=options.artifact_dir) as client:
            run = client.start(
                agent=Agent(target, connection),
                cases=[Sample(inputs={"query": options.prompt})],
                load=Load(
                    concurrency=options.concurrency,
                    duration_seconds=options.duration,
                    max_requests=options.max_requests,
                    timeout_seconds=options.timeout,
                ),
            )
            try:
                report = run.wait(timeout=budget_record(options)["wait_timeout_seconds"])
            except RunFailed as failure:
                report = failure.report
            metrics = report.run.metrics
            probe_attempts = int(report.run.preflight.request_id is not None)
            measured_attempts = metrics.get("requests", 0)
            succeeded = (
                report.run.preflight.status == "passed"
                and report.run.load_status == "completed"
                and metrics.get("successful_requests", 0) > 0
                and metrics.get("error_rate") == 0
            )
            record = {
                **budget_record(options),
                "run_id": str(run.id),
                "status": report.run.status,
                "inference_preflight": report.run.preflight.status,
                "preflight_error": report.run.preflight.error.model_dump(mode="json")
                if report.run.preflight.error is not None
                else None,
                "load_status": report.run.load_status,
                "profiling_status": report.run.profiling_status,
                "evaluation_readiness": report.run.evaluation_preflight.status,
                "evaluation_status": report.run.evaluation_status,
                "observed_probe_attempts": probe_attempts,
                "observed_measured_attempts": measured_attempts,
                "observed_total_attempts": probe_attempts + measured_attempts,
                "fail_fast_confirmed": (
                    report.run.preflight.status == "failed"
                    and report.run.load_status == "skipped"
                    and measured_attempts == 0
                ),
                "passed": succeeded,
                "metrics": {
                    "requests": measured_attempts,
                    **{
                        name: metrics[name]
                        for name in (
                            "successful_requests",
                            "error_rate",
                            "elapsed_seconds_including_drain",
                            "configured_concurrency",
                            "observed_peak_in_flight",
                        )
                        if name in metrics
                    },
                },
            }
            atomic_json(options.artifact_dir / "validation.json", record)
            return (0 if succeeded else 1), record


def main(arguments: Sequence[str] | None = None) -> int:
    """Print the dry-run budget or a safe live result; never echo private selections."""
    options = parse_options(arguments)
    if not options.live:
        print(json.dumps(budget_record(options), indent=2))
        return 0
    try:
        code, record = execute(options)
    except Exception:  # noqa: BLE001 - SDK/provider errors can contain private values
        print("App smoke check failed before a usable report; inspect operator configuration.")
        return 2
    print(json.dumps(record, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
