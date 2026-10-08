"""Consent-gated native App quality integration using captured policy answers.

Dry-run is the default. Live execution requires an exact selected OAuth profile,
App name, an empty protected artifact directory, --live and --accept-paid-traffic.
One synthetic policy case has an authoritative reference, explicit relevance and
correctness, no automatic planner, and the frozen databricks-gpt-5-4-mini judge.
The one Locust engine sends one excluded probe and at most two measured requests.
Judges assess captures, never reinvoke the target. Current frozen settings allow
two zero-retry readiness assessments and at most four quality assessments with
two retries each: at most fourteen judge-provider attempts, each capped at 2048
output tokens. This is not a dollar quota, calibration, or capacity validation.

Native MLflow tracks only in the dedicated local directory. Protected raw answers,
references and judge rationales are retained there; console/validation summaries
contain phase outcomes, counts and boolean verdicts, never rationales or credentials.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import databricks_app_smoke as smoke

JUDGE_MODEL = "databricks-gpt-5-4-mini"
POLICY_PROMPT = (
    "Policy: Unopened items may be returned within 30 days; opened items cannot be refunded. "
    "Can an opened item be refunded? Answer in one short sentence."
)
EXPECTED_FACT = "Opened items cannot be refunded."
SCORERS = ("relevance", "correctness")


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse explicit selections and reuse the smoke consent/input bounds without I/O.

    Args:
        arguments: CLI arguments; None uses the current process arguments.

    Returns:
        Smoke-compatible options restricted to two measured calls and ten seconds.

    Raises:
        SystemExit: Selection, workload limits, or live consent are invalid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--concurrency", type=int, default=1, help="Closed-loop users, 1..5.")
    parser.add_argument("--duration", type=float, default=10, help="Dispatch seconds, 0.1..10.")
    parser.add_argument("--timeout", type=float, default=60, help="Per-attempt seconds, 0.1..60.")
    parser.add_argument("--max-requests", type=int, choices=(1, 2), default=2)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    selected = parser.parse_args(arguments)
    if selected.duration > 10:
        parser.error("--duration must be at most ten seconds for this quality check")
    delegated = [
        "--profile",
        selected.profile,
        "--app-name",
        selected.app_name,
        "--prompt",
        POLICY_PROMPT,
        "--concurrency",
        str(selected.concurrency),
        "--duration",
        str(selected.duration),
        "--timeout",
        str(selected.timeout),
        "--max-requests",
        str(selected.max_requests),
    ]
    if selected.artifact_dir is not None:
        delegated.extend(["--artifact-dir", str(selected.artifact_dir)])
    if selected.live:
        delegated.append("--live")
    if selected.accept_paid_traffic:
        delegated.append("--accept-paid-traffic")
    return smoke.parse_options(delegated)


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Describe the hard request/token caps, excluding selected identities and content."""
    quality = len(SCORERS) * options.max_requests
    return {
        **smoke.budget_record(options),
        "evaluation_mode": "explicit",
        "scorers": list(SCORERS),
        "judge_model": JUDGE_MODEL,
        "automatic_planner_calls": 0,
        "max_scored_requests_per_scorer": 2,
        "max_judge_readiness_assessments": len(SCORERS),
        "max_judge_quality_assessments": quality,
        "judge_readiness_max_retries": 0,
        "judge_quality_max_retries": 2,
        "max_judge_provider_attempts": len(SCORERS) + quality * 3,
        "judge_max_completion_tokens_per_attempt": 2048,
        "judge_timeout_seconds_per_attempt": 60,
        "wait_timeout_seconds": 1200,
        "judge_calibration_established": False,
    }


def _record(options: argparse.Namespace, report: Any) -> tuple[int, dict[str, Any]]:
    """Reduce native report evidence to phase/count/verdict-only validation results.

    Args:
        options: Consented bounded workload.
        report: Actual public facade RunReport; captures/rationales are not exported.

    Returns:
        Exit zero only for complete execution and all observed boolean verdicts true.
        Valid false verdicts are quality failures, not transport failures. Missing
        criteria/assessments or lifecycle failures remain unavailable evidence.
    """
    metrics = report.run.metrics
    measured = metrics.get("requests", 0)
    probe = int(report.run.preflight.request_id is not None)
    evaluations = report.run.evaluation.get("results", [])
    summaries = [
        {
            "scorer": item.get("scorer"),
            "status": item.get("status"),
            "attempted": item.get("attempted", 0),
            "scored": item.get("scored", 0),
            "judge_errors": item.get("judge_errors", 0),
            "pass_rate": item.get("pass_rate"),
            "verdicts": [
                assessment["value"]
                for assessment in item.get("assessments", [])
                if type(assessment.get("value")) is bool
            ],
        }
        for item in evaluations
        if item.get("scorer") in SCORERS
    ]
    complete = (
        report.run.preflight.status == "passed"
        and report.run.evaluation_preflight.status == "passed"
        and report.run.load_status == "completed"
        and metrics.get("measurement_complete") is True
        and metrics.get("successful_requests", 0) > 0
        and metrics.get("error_rate") == 0
        and report.run.evaluation_status == "completed"
        and {item["scorer"] for item in summaries} == set(SCORERS)
        and all(
            item["status"] == "completed"
            and item["scored"] > 0
            and item["scored"] == len(item["verdicts"])
            and item["judge_errors"] == 0
            for item in summaries
        )
    )
    passed = complete and all(all(item["verdicts"]) for item in summaries)
    return (0 if passed else 1), {
        **budget_record(options),
        "run_id": report.run.id,
        "status": report.run.status,
        "inference_preflight": report.run.preflight.model_dump(mode="json"),
        "evaluation_readiness": report.run.evaluation_preflight.model_dump(mode="json"),
        "load_status": report.run.load_status,
        "profiling_status": report.run.profiling_status,
        "evaluation_status": report.run.evaluation_status,
        "observed_probe_attempts": probe,
        "observed_measured_attempts": measured,
        "observed_total_target_attempts": probe + measured,
        "evaluation_execution_complete": complete,
        "quality_outcome": "passed" if passed else "failed" if complete else "unavailable",
        "passed": passed,
        "scorer_results": summaries,
        "metrics": {
            "requests": measured,
            **{
                name: metrics[name]
                for name in ("successful_requests", "error_rate", "configured_concurrency")
                if name in metrics
            },
        },
    }


def execute(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Execute one consented quality run through public local facade and native MLflow.

    Args:
        options: Live options restricted to ten dispatch seconds/two measured calls.

    Returns:
        Exit code and content-free validation record, persisted as validation.json.

    Raises:
        ValueError: Missing consent or nonempty store, before discovery/traffic.
        Exception: SDK resolution, ownership or provider setup fails before a report;
            main suppresses raw exception values. SDK/auth wall time is not hard bounded.

    Side Effects:
        Authorized OAuth/App resolution, one probe, up to two measured target calls,
        and bounded mini judging can incur spend. Judging uses captures only. Creates
        a local SQLite MLflow experiment and protected artifacts under the selected
        directory; never deploys resources. Operator settings stay task-local, but
        the existing native evaluation backend updates MLflow's process-global
        tracking selector and its environment variable. Run this CLI in a separate
        process rather than treating execute as an isolated embedded-library API.
    """
    if not options.live or not options.accept_paid_traffic or options.artifact_dir is None:
        raise ValueError("Live validation requires explicit consent and a dedicated store")
    if options.artifact_dir.exists() and any(options.artifact_dir.iterdir()):
        raise ValueError("Use a new or empty dedicated artifact directory")
    if options.max_requests > 2 or options.duration > 10:
        raise ValueError("Quality validation permits at most two measured calls and ten seconds")
    from mlflow.tracking import MlflowClient

    from benchmark_agents.configuration import configured_environment
    from benchmark_agents.settings import ConnectionSettings, ProviderSettings, Settings
    from benchmark_agents.storage import atomic_json
    from benchmark_agents.target_resolver import resolve_registered_target
    from evalsurge import Agent, EvalSurge, Evaluation, Load, RunFailed, Sample

    destination = options.artifact_dir.resolve()
    tracking_uri = f"sqlite:///{destination / 'quality-mlflow.db'}"
    settings = Settings(
        artifact_dir=destination,
        tracking_uri=tracking_uri,
        provider=ProviderSettings(profile=options.profile, judge_model=JUDGE_MODEL),
        connections={
            "sample": ConnectionSettings(
                kind="databricks-app",
                app_name=options.app_name,
                profile=options.profile,
                protocols=("databricks-agent-runtime",),
            )
        },
    )
    values = settings.to_environment()
    values.pop("MLFLOW_EXPERIMENT_ID", None)
    values["MLFLOW_MODEL_CATALOG_URI"] = ""
    values["MLFLOW_ENABLE_ASYNC_TRACE_LOGGING"] = "false"
    with configured_environment(values):
        # Same resolver/ambient-override guard as smoke; this never invokes a target.
        target, connection = resolve_registered_target("sample", settings.connections)
        with EvalSurge.local(artifact_dir=destination) as client:
            # The public context owns the storage lock before MLflow creates files.
            store = MlflowClient(tracking_uri=tracking_uri)
            values["MLFLOW_EXPERIMENT_ID"] = store.create_experiment(
                "evalsurge-app-quality",
                artifact_location=(destination / "mlflow-artifacts").as_uri(),
            )
            run = client.start(
                agent=Agent(target, connection),
                cases=[
                    Sample(
                        inputs={"query": POLICY_PROMPT},
                        expectations={"expected_facts": [EXPECTED_FACT]},
                    )
                ],
                load=Load(
                    concurrency=options.concurrency,
                    duration_seconds=options.duration,
                    max_requests=options.max_requests,
                    timeout_seconds=options.timeout,
                ),
                evaluation=Evaluation(
                    description="Answer the synthetic refund policy accurately and relevantly",
                    scorers=list(SCORERS),
                    registered_scorers=[],
                    max_scored_requests=2,
                ),
            )
            try:
                report = run.wait(timeout=budget_record(options)["wait_timeout_seconds"])
            except RunFailed as failure:
                report = failure.report
            code, record = _record(options, report)
            atomic_json(destination / "validation.json", record)
            return code, record


def main(arguments: Sequence[str] | None = None) -> int:
    """Print dry-run budget or safe live result, with no profile/App/content disclosure."""
    options = parse_options(arguments)
    if not options.live:
        print(json.dumps(budget_record(options), indent=2))
        return 0
    try:
        code, record = execute(options)
    except Exception:  # noqa: BLE001 - SDK/provider exceptions can include private values
        print("App quality check failed before a usable report; inspect operator configuration.")
        return 2
    print(json.dumps(record, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
