"""Consent-gated endpoint journeys; dry-run never imports an agent or contacts it.

Uses the public unified SDK and the existing sole Locust engine. The target must
already be deployed/running and perform actual model calls. Framework and model
labels are operator declarations, not automatically verified hosting evidence.
This script does not deploy Apps, install frameworks, run notebooks, configure
judges, or turn an endpoint observation into a sustainable-capacity claim.
"""

import argparse
import json
import math
import os
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_TERMINAL = {"completed", "completed_with_gaps", "failed", "cancelled", "interrupted"}
_PREFLIGHT_CODES = {
    "authentication_failed",
    "target_http_error",
    "target_timeout",
    "target_connection_error",
    "invalid_stream",
    "invalid_response",
    "worker_failed",
}


def _endpoint(value: str, *, origin: bool = False) -> str:
    """Validate a secret-free HTTPS or loopback HTTP endpoint without DNS lookup.

    Args:
        value: Operator-selected URL, never a credential-bearing URL.
        origin: Require an origin for the optional EvalSurge service.

    Returns:
        URL with a service-origin trailing slash removed when requested.

    Raises:
        ValueError: URL has credentials, query/fragment, an unsafe scheme or path.
    """
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Select an authorized secret-free endpoint") from None
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.hostname
        or parsed.scheme not in {"https", "http"}
        or (parsed.scheme == "http" and not local)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port == 0
        or (origin and parsed.path not in {"", "/"})
    ):
        raise ValueError("Select an authorized secret-free endpoint")
    return value.rstrip("/") if origin else value


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse explicit bounded selections without auth, source execution or traffic.

    Args:
        arguments: Explicit CLI arguments, or None for the process argv.

    Returns:
        Operator selections; framework labels never become an import/allowlist.

    Raises:
        SystemExit: A selector, finite bound or explicit live consent is invalid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=("http", "app", "remote"))
    parser.add_argument("--framework", required=True, help="Declared deployed implementation.")
    parser.add_argument(
        "--model", required=True, help="Declared model; never an inferred fallback."
    )
    parser.add_argument("--url", help="Already running http-json inference endpoint.")
    parser.add_argument("--app-name", help="Already deployed DurableAgentServer App.")
    parser.add_argument("--profile", help="Exact selected profile, required for App discovery.")
    parser.add_argument("--service-url", help="Existing authorized EvalSurge API origin.")
    parser.add_argument("--connection-id", help="Operator-registered remote target ID.")
    parser.add_argument("--api-key-env", help="Optional operator-owned service key variable.")
    parser.add_argument(
        "--source-revision", help="Deployed agent source identity, not source text."
    )
    parser.add_argument("--scenario", choices=("load", "fail-fast", "cancel"), default="load")
    parser.add_argument("--intentional-rejection", action="store_true")
    parser.add_argument("--expected-preflight-code", choices=sorted(_PREFLIGHT_CODES))
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--max-requests", type=int, default=5)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    parser.add_argument("--real-inference-attested", action="store_true")
    options = parser.parse_args(arguments)
    if options.scenario == "fail-fast" and not (
        options.intentional_rejection and options.expected_preflight_code
    ):
        parser.error("fail-fast requires --intentional-rejection and --expected-preflight-code")
    if options.scenario != "fail-fast" and (
        options.intentional_rejection or options.expected_preflight_code
    ):
        parser.error("Intentional rejection selectors apply only to the fail-fast scenario")
    for name in ("framework", "model", "profile", "source_revision", "connection_id"):
        value = getattr(options, name)
        if value is not None and (not value.strip() or len(value) > 512):
            parser.error(f"--{name.replace('_', '-')} must be a bounded explicit selection")
    if not 1 <= options.concurrency <= 5 or not 1 <= options.max_requests <= 20:
        parser.error("--concurrency must be 1..5 and --max-requests 1..20")
    for name, maximum in (("duration", 180), ("timeout", 60)):
        if (
            not math.isfinite(getattr(options, name))
            or not 0.1 <= getattr(options, name) <= maximum
        ):
            parser.error(f"--{name} must be finite, between 0.1 and {maximum} seconds")
    selectors = {
        "http": ("url",),
        "app": ("app_name", "profile"),
        "remote": ("service_url", "connection_id"),
    }
    for name in selectors[options.target]:
        if not getattr(options, name):
            parser.error(f"--{options.target} target requires --{name.replace('_', '-')}")
    unrelated = {
        "http": ("app_name", "profile", "service_url", "connection_id", "api_key_env"),
        "app": ("url", "service_url", "connection_id", "api_key_env"),
        "remote": ("url", "app_name", "profile"),
    }
    if any(getattr(options, name) is not None for name in unrelated[options.target]):
        parser.error("Remove selectors for a different target; no selector is silently ignored")
    try:
        if options.url:
            options.url = _endpoint(options.url)
        if options.service_url:
            options.service_url = _endpoint(options.service_url, origin=True)
    except ValueError as error:
        parser.error(str(error))
    if options.app_name and not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", options.app_name):
        parser.error("--app-name must identify one existing authorized App")
    if options.api_key_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", options.api_key_env):
        parser.error("--api-key-env must name an operator-owned environment variable")
    if options.live and not (
        options.accept_paid_traffic
        and options.real_inference_attested
        and options.artifact_dir
        and options.source_revision
    ):
        parser.error(
            "--live requires --accept-paid-traffic, --real-inference-attested, "
            "--source-revision and a new --artifact-dir"
        )
    return options


def plan_record(options: argparse.Namespace) -> dict[str, Any]:
    """Describe one bounded journey, not proof of its deployment or inference.

    Args:
        options: Validated explicit selectors; no resolved token is accepted.

    Returns:
        Content-free plan with one excluded probe and a finite measured ceiling.
        Provider-native tool/model retries can add calls inside each invocation.
    """
    return {
        "target": options.target,
        "declared_framework": options.framework,
        "declared_model": options.model,
        "declared_source_revision": options.source_revision,
        "profile": options.profile,
        "app_name": options.app_name,
        "connection_id": options.connection_id,
        "scenario": options.scenario,
        "negative_test_only": options.scenario == "fail-fast",
        "expected_preflight_code": options.expected_preflight_code,
        "concurrency": options.concurrency,
        "dispatch_seconds": options.duration,
        "per_attempt_timeout_seconds": options.timeout,
        "max_measured_attempts": options.max_requests,
        "max_excluded_probe_attempts": 1,
        "max_total_target_attempts": options.max_requests + 1,
        "evaluation_mode": "off",
        "runner_location": "service host" if options.target == "remote" else "Python caller",
        "live_requested": options.live,
        "actual_inference_operator_attested": options.real_inference_attested,
        "target_source_automatically_verified": False,
        "model_calls_per_invocation_bounded": False,
        "monetary_quota_enforced": False,
        "sustainable_capacity_established": False,
        "inflight_cancellation_confirmed": False,
    }


def retrieval_evidence(
    run_id: Any, status: Any, result: Any, report: Any, retrieved: Any, *, remote: bool
) -> dict[str, Any]:
    """Compare native typed receipts without traffic or exporting protected values.

    Args:
        run_id: SDK-owned run identifier.
        status: Retrieved typed polling metadata.
        result: Retrieved typed result.
        report: Report returned by wait or its terminal failure exception.
        retrieved: Independently retrieved typed report page.
        remote: Whether work is service owned and could outlive this client.

    Returns:
        Identity comparison, terminal-state/phase consistency, full result/report
        equality and the safe preflight code only. Nonterminal or inconsistent
        evidence cannot claim terminal retrieval parity or stopped remote work.
        These are schema/evidence comparisons, not successful model inference.
    """
    identities = status.id == result.id == report.run.id == retrieved.run.id == run_id
    outcomes = (status, result, report.run, retrieved.run)
    terminal = all(item.status in _TERMINAL for item in outcomes)
    states = all(item.status == result.status for item in outcomes)
    phases = all(item.phases == result.phases for item in outcomes)
    result_equal = result == report.run == retrieved.run
    report_equal = report == retrieved
    parity = identities and terminal and states and phases and result_equal and report_equal
    error = report.run.preflight.error
    code = getattr(error, "code", None)
    return {
        "identifiers_agree": identities,
        "terminal_states_and_phases_agree": terminal and states and phases,
        "result_payloads_agree": result_equal,
        "report_pages_agree": report_equal,
        "retrieval_agrees": parity,
        "remote_work_may_remain_active": remote and not parity,
        "preflight_code": code if code in _PREFLIGHT_CODES else None,
    }


def scenario_passed(options: argparse.Namespace, receipt: dict[str, Any]) -> bool:
    """Classify receipt metadata, not model quality or successful negative inference.

    Args:
        options: Explicit scenario including the intentional rejection declaration.
        receipt: Content-free terminal retrieval/evidence projection.

    Returns:
        Whether the requested scenario and actual terminal parity are established.
        Expected fail-fast is a failed operational run, not successful inference.
    """
    if not receipt.get("retrieval_agrees"):
        return False
    metrics = receipt.get("metrics")
    if options.scenario == "fail-fast":
        return bool(
            options.intentional_rejection
            and receipt.get("preflight_code") == options.expected_preflight_code
            and receipt.get("status") == "failed"
            and receipt.get("preflight") == "failed"
            and receipt.get("phases", {}).get("load") == "skipped"
            and (metrics is None or metrics["requests"] == 0)
        )
    if options.scenario == "cancel":
        return bool(
            receipt.get("cancellation_ack") == "cancellation_requested"
            and receipt.get("status") == "cancelled"
        )
    return bool(
        receipt.get("preflight") == "passed"
        and receipt.get("phases", {}).get("load") == "completed"
        and metrics is not None
        and metrics["successful_requests"] > 0
        and metrics["error_rate"] == 0
    )


def execute(options: argparse.Namespace) -> dict[str, Any]:
    """Run an explicitly consented existing endpoint through the public SDK.

    Args:
        options: Live selections with paid-traffic consent and inference attestation.

    Returns:
        Content-free receipt. Failed preflights stay failed; no retries or model
        substitutions occur. Cancellation acknowledges dispatch-stop/drain only,
        not termination of an agent's background work or proven in-flight coverage.

    Raises:
        ValueError: Live consent, fresh storage or a selected service key is absent.
        Exception: SDK/startup/retrieval fails; the incomplete receipt is retained.

    Side Effects:
        Makes actual target calls and can execute tools/incur spend. Direct mode
        owns one normal coordinator/Locust through its context. Remote context
        closure does not cancel service-owned work. Protected artifacts are kept;
        no agent/framework code is imported and no remote resource is deployed.
    """
    if not (
        options.live
        and options.accept_paid_traffic
        and options.real_inference_attested
        and options.artifact_dir
        and options.source_revision
    ):
        raise ValueError("Live validation requires fresh explicit consent and target identity")
    directory = options.artifact_dir.absolute()
    if directory.exists() or directory.is_symlink():
        raise ValueError("Select new storage; previous evidence is never overwritten")
    api_key = os.environ.get(options.api_key_env) if options.api_key_env else None
    if options.api_key_env and not api_key:
        raise ValueError("The selected operator-owned service key is unavailable")
    from benchmark_agents.storage import atomic_json
    from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

    directory.mkdir(parents=True, mode=0o700)
    receipt = {
        **plan_record(options),
        "passed": False,
        "retrieval_agrees": False,
        "remote_work_may_remain_active": options.target == "remote",
    }
    receipt_path = directory / "hosted-journey.json"
    atomic_json(receipt_path, receipt)
    if options.target == "remote":
        client = EvalSurge.remote(options.service_url, api_key=api_key, typed=True)
        identifier = options.connection_id
    else:
        binding = (
            Agent.http(options.url, protocol="http-json")
            if options.target == "http"
            else Agent.databricks_app(options.app_name, profile=options.profile)
        )
        client = EvalSurge(artifact_dir=directory / "runs", targets={"agent": binding})
        identifier = "agent"
    request = RunCreate(
        target=TargetReference(connection_id=identifier),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(
            concurrency=options.concurrency,
            max_requests=options.max_requests,
            duration_seconds=options.duration,
            timeout_seconds=options.timeout,
        ),
    )
    try:
        with client:
            run = client.start(request)
            receipt["run_id"] = str(run.id)
            atomic_json(receipt_path, receipt)
            wait_bound = options.duration + 2 * options.timeout + 120
            if options.scenario == "cancel":
                deadline = time.monotonic() + wait_bound
                while time.monotonic() < deadline:
                    status = run.status()
                    if status.status == "running":
                        receipt["cancellation_ack"] = run.cancel().status
                        break
                    if status.status in _TERMINAL:
                        break
                    time.sleep(0.1)
            try:
                report = run.wait(timeout=wait_bound)
            except Exception as error:  # noqa: BLE001 - retain safe terminal reports
                if getattr(error, "report", None) is None:
                    raise
                report = error.report
            code = getattr(report.run.preflight.error, "code", None)
            receipt.update(
                status=report.run.status,
                phases=report.run.phases.model_dump(mode="json"),
                preflight=report.run.preflight.status,
                preflight_code=code if code in _PREFLIGHT_CODES else None,
            )
            # Retain safe failure evidence even when a later retrieval fails.
            atomic_json(receipt_path, receipt)
            status, result, retrieved = run.status(), run.result(), run.report()
            receipt.update(
                metrics=result.metrics.model_dump(mode="json") if result.metrics else None,
            )
            receipt.update(
                retrieval_evidence(
                    run.id, status, result, report, retrieved, remote=options.target == "remote"
                )
            )
            receipt["passed"] = scenario_passed(options, receipt)
    finally:
        atomic_json(receipt_path, receipt)
    return receipt


def main(arguments: Sequence[str] | None = None) -> int:
    """Print dry bounds or a content-free receipt; never print provider exceptions."""
    options = parse_options(arguments)
    if not options.live:
        print(json.dumps(plan_record(options), indent=2))
        return 0
    try:
        receipt = execute(options)
    except Exception:  # noqa: BLE001 - detailed evidence remains protected, no unsafe stdout
        retained = bool(
            options.artifact_dir and (options.artifact_dir / "hosted-journey.json").is_file()
        )
        print(
            json.dumps(
                {"passed": False, "error": "hosted_journey_failed", "evidence_retained": retained}
            )
        )
        return 1
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
