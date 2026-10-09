"""Review-only serverless load-generator -> deployed App authentication gate.

The notebook runs EvalSurge/Locust only; all agent/model execution stays inside
the selected deployed App. This module never imports customer agent frameworks,
starts an agent helper or exports notebook credentials. Current profile-only App
binding and native notebook OAuth worker availability are separate prerequisites.
Selecting the name of a laptop profile does not install that identity in a Job.

No live submission is implied by this file. A maintainer must review the current
wheel, deployed source/output limit and supported portable OAuth setup before
approving this initial <=1 preflight + <=1 measured App-invocation smoke test.
That bound is on invocations, not arbitrary agent model/tool turns or money.
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from benchmark_agents.v2_models import RunCreate

_WORKER_CHECK = """
import json
import sys
from benchmark_agents.connections import Connection
from benchmark_agents.target_resolver import app_authentication
try:
    connection = Connection.model_validate_json(sys.argv[1])
    headers = app_authentication(connection)()
    ready = bool(headers.get('Authorization'))
    print(json.dumps({'worker_oauth_ready': ready}))
except Exception:
    print(json.dumps({'worker_oauth_ready': False}))
"""


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Validate exact operator selections without auth, deployment or inference.

    Args:
        arguments: Explicit CLI arguments; omission reads process argv.

    Returns:
        Reviewed selections with fixed two-invocation and token-declaration bounds.

    Raises:
        SystemExit: Required selection, consent or fixed bound is invalid.

    The output-token bound is an attestation about deployed agent configuration,
    not a field sent to the App. The serving contract owns its model token limit.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--deployed-max-output-tokens", type=int, default=512)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    parser.add_argument("--real-inference-attested", action="store_true")
    options = parser.parse_args(arguments)
    try:
        parsed = urlsplit(options.workspace)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"}
            and parsed.port in {None, 443}
        )
    except ValueError:
        valid = False
    if not valid:
        parser.error("--workspace must be the exact selected HTTPS workspace origin")
    options.workspace = options.workspace.rstrip("/")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", options.app_name):
        parser.error("--app-name must select one already deployed authorized App")
    for name in ("profile", "target_model", "source_revision"):
        value = getattr(options, name)
        if not value.strip() or len(value) > 512:
            parser.error(f"--{name.replace('_', '-')} must be an explicit bounded selection")
    if not 1 <= options.deployed_max_output_tokens <= 512:
        parser.error("The reviewed deployed model output limit must be 1..512 tokens")
    if options.live and not (
        options.accept_paid_traffic and options.real_inference_attested and options.artifact_dir
    ):
        parser.error(
            "--live requires --accept-paid-traffic, --real-inference-attested "
            "and dedicated --artifact-dir; maintainer auth/traffic review remains required"
        )
    return options


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Describe the intended topology/bounds; declarations are not live evidence."""
    return {
        "runner": "serverless-notebook",
        "target_hosting": "deployed-databricks-app",
        "app_name": options.app_name,
        "workspace": options.workspace,
        "declared_model": options.target_model,
        "declared_source_revision": options.source_revision,
        "declared_deployed_max_output_tokens": options.deployed_max_output_tokens,
        "concurrency": 1,
        "max_requests": 1,
        "maximum_app_invocations": 2,
        "evaluation": "off",
        "native_notebook_driver_auth_is_worker_evidence": False,
        "api_execution_tested": False,
        "deployed_app_tested": False,
        "paid_traffic_authorized_by_this_record": False,
    }


def request() -> "RunCreate":
    """Build one measured attempt plus the existing excluded target preflight.

    This smoke checks the runner/target boundary, not capacity. No scorer planner,
    judge or target-model fallback is configured; references/answers are retained
    by the normal protected report store, never exported in the safe receipt.
    """
    from evalsurge import Case, Load, RunCreate, TargetReference

    return RunCreate(
        name="serverless-runner-databricks-app-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Reply briefly: can an opened item be refunded?"})],
        load=Load(concurrency=1, duration_seconds=5, max_requests=1, timeout_seconds=30),
    )


def readiness(options: argparse.Namespace) -> dict[str, Any]:
    """Check the existing profile-bound driver and independent worker without inference.

    Args:
        options: Exact operator App/profile selectors previously validated.

    Returns:
        Content-free booleans and fixed actionable blockers. No token, SDK message,
        profile content, raw child output or headers are returned.

    Side Effects:
        When the profile/ambient-override guard permits admission, may make bounded
        OAuth and App metadata reads in driver and worker. It never sends an agent
        request or modifies the environment. Child process has a 30-second limit.
        OAuth providers can outlive SDK nominal driver metadata timeout budgets.

    Native notebook runtime-OAuth is not copied to the child. The child must own a
    supported refreshable OAuth source itself, using the unchanged public binding.
    No missing profile is generated or read from a laptop as a workaround.
    """
    from benchmark_agents.providers import workspace_client
    from benchmark_agents.target_resolver import TargetResolutionError, resolve_registered_target
    from evalsurge import Agent

    agent = Agent.databricks_app(options.app_name, profile=options.profile)
    result: dict[str, Any] = {
        "driver_profile_ready": False,
        "worker_oauth_ready": False,
        "inference_invocations": 0,
        "blockers": [],
    }
    try:
        _, connection = resolve_registered_target("agent", {"agent": agent.registration})
    except TargetResolutionError:
        result["blockers"].append(
            "Current App binding needs an exact portable OAuth profile and rejects ambient "
            "notebook destination/identity overrides. Native driver OAuth alone cannot bind "
            "this profile. No token copying or override-guard bypass is supported."
        )
        return result
    try:
        workspace_matches = (
            workspace_client(profile=options.profile).config.host.rstrip("/") == options.workspace
        )
    except Exception:  # noqa: BLE001 - provider messages may contain private configuration
        workspace_matches = False
    if not workspace_matches:
        result["blockers"].append(
            "Selected profile does not establish the explicitly approved workspace. "
            "No alternate profile, host or authentication fallback is permitted."
        )
        return result
    result["driver_profile_ready"] = True
    try:
        child = subprocess.run(
            [sys.executable, "-c", _WORKER_CHECK, connection.model_dump_json()],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        checked = json.loads(child.stdout.splitlines()[-1]) if child.returncode == 0 else {}
        result["worker_oauth_ready"] = checked.get("worker_oauth_ready") is True
    except (subprocess.TimeoutExpired, ValueError, IndexError, OSError):
        result["worker_oauth_ready"] = False
    if not result["worker_oauth_ready"]:
        result["blockers"].append(
            "Independent Locust worker has no verified refreshable App OAuth source. "
            "Driver-native runtime-OAuth depends on notebook context unavailable to that "
            "subprocess. Stop before load; request a reviewed operator-auth design."
        )
    return result


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """After consent/auth gates, run the generator-only two-invocation smoke test.

    Args:
        options: Previously validated exact selections and explicit live consent.

    Returns:
        Safe receipt including independent retrieval consistency, never raw answers.
        An auth failure returns ``blocked`` with zero inference, not a passed Job.

    Raises:
        PermissionError: Consent/attestation is absent, before auth/network calls.
        ValueError: Artifacts path is not empty, before inference.

    Side Effects:
        Uses existing coordinator/Locust subprocess and protected local storage.
        Up to two App invocations; the deployed source must enforce declared model
        limits. Context exit cleans runner lifecycle, not App/Lakebase resources.
    """
    if not (
        options.live
        and options.accept_paid_traffic
        and options.real_inference_attested
        and options.artifact_dir is not None
    ):
        raise PermissionError("Explicit reviewed live consent is required before auth or traffic")
    path = options.artifact_dir
    if path.exists() and any(path.iterdir()):
        raise ValueError("Select an empty dedicated artifacts directory")
    receipt = {**budget_record(options), "passed": False, "state": "not_started"}
    checked = await asyncio.to_thread(readiness, options)
    receipt["authentication"] = checked
    if checked["blockers"]:
        return {**receipt, "state": "blocked", "inference_invocations": 0}

    from evalsurge import Agent, EvalSurge, RunFailed

    from .hosted_journeys import retrieval_evidence

    async with EvalSurge.local_async(
        artifact_dir=path,
        targets={"agent": Agent.databricks_app(options.app_name, profile=options.profile)},
    ) as client:
        handle = await client.start(request())
        try:
            report = await handle.wait(timeout=120)
        except RunFailed as error:
            report = error.report
        state = await handle.status()
        result = await handle.result()
        fetched = await handle.report()
        evidence = retrieval_evidence(handle.id, state, result, report, fetched, remote=False)
        receipt["retrieval"] = evidence
        receipt["run_id"] = str(handle.id)
        receipt["state"] = report.run.status
        receipt["deployed_app_tested"] = True
        receipt["passed"] = (
            report.run.status == "completed"
            and evidence["retrieval_agrees"]
            and result.metrics is not None
            and result.metrics.successful_requests == 1
            and result.metrics.error_rate == 0
        )
    receipt["runner_context_closed"] = True
    return receipt
