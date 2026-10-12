"""Pure configuration inventory: fifteen requested framework/target/runner cells.

This module never invokes an agent, authenticates, starts a worker, or deploys an
App. Framework names classify customer-owned agents; they do not select EvalSurge
adapters. Serverless notebook validation targets deployed Apps only; the retained
HTTP notebook is optional and outside this requested inventory. All fifteen
cells remain fresh-live-validation gates. Runner-App HTTP cells are conditional
on approved reachable HTTPS endpoints, never a laptop's loopback address.
"""

import argparse
import ipaddress
import json
import re
from dataclasses import dataclass
from itertools import product
from typing import Literal
from urllib.parse import urlsplit

from evalsurge import Agent, Case, Connection, EvaluationPolicy, Load, RunCreate, TargetReference

Framework = Literal["crewai", "langgraph", "openai-agents"]
RunnerLocation = Literal["local", "serverless-notebook", "databricks-app"]
TargetHosting = Literal["http", "databricks-app"]
FRAMEWORKS: tuple[Framework, ...] = ("crewai", "langgraph", "openai-agents")
RUNNERS: tuple[RunnerLocation, ...] = ("local", "serverless-notebook", "databricks-app")
TARGETS: tuple[TargetHosting, ...] = ("http", "databricks-app")
SAMPLE_QUERY = "Can an opened item be refunded?"
SAMPLE_REFERENCE = "Opened items cannot be refunded."


@dataclass(frozen=True)
class Journey:
    """A logical sample label, not evidence that execution or inference succeeded."""

    framework: Framework
    runner: RunnerLocation
    hosting: TargetHosting

    def __post_init__(self) -> None:
        """Reject misspelled labels without importing any customer framework."""
        if (
            self.framework not in FRAMEWORKS
            or self.runner not in RUNNERS
            or self.hosting not in TARGETS
        ):
            raise ValueError("Choose an explicit framework, runner location, and target hosting")
        if self.runner == "serverless-notebook" and self.hosting != "databricks-app":
            raise ValueError("Requested serverless notebook validation targets deployed Apps only")

    @property
    def id(self) -> str:
        """Return a stable label suitable for a protected run's name/artifact directory."""
        return f"{self.runner}__{self.hosting}__{self.framework}"


def journeys() -> tuple[Journey, ...]:
    """Return fifteen requested combinations without claiming live product support.

    Serverless notebooks select deployed Apps only. Runner-App/HTTP combinations
    remain conditional on an operator-approved reachable HTTPS endpoint. A
    laptop's localhost endpoint is not made reachable by this module; no tunnel,
    port forward, DNS lookup, or network probe is performed.
    """
    return tuple(
        Journey(framework, runner, hosting)
        for framework, runner, hosting in product(FRAMEWORKS, RUNNERS, TARGETS)
        if not (runner == "serverless-notebook" and hosting == "http")
    )


def request(
    journey: Journey,
    *,
    evaluation: Literal["off", "explicit"] = "off",
    case: Case | None = None,
    sample_refund_policy: bool = False,
) -> RunCreate:
    """Construct the same v2 workload with optional captured-answer judging.

    Args:
        journey: Labels used only for the run name, never framework routing.
        evaluation: Off by default; explicit selects relevance and correctness.
            Automatic planning is deliberately not selected by this helper.
        case: Optional caller-owned input/reference. Explicit evaluation requires
            a nonempty reference; this function cannot establish its authority.
        sample_refund_policy: Explicitly affirm the selected agent implements the
            exact synthetic policy in examples/real_framework_handler.py. Only then
            may explicit evaluation supply its opened-item reference. Must not be
            mixed with a caller-owned case or supplied when evaluation is off.

    Returns:
        One measured attempt at concurrency one, up to ten seconds of dispatch,
        and a forty-second per-attempt timeout. One additional excluded inference
        preflight precedes measured load. Explicit judging selects at most one
        measured capture per scorer, separately from excluded judge readiness.

    Raises:
        ValueError: Unsupported policy, contradictory reference selection, or an
            explicit policy without caller-owned evidence/confirmed sample truth.

    Side Effects:
        None. Building this object is schema validation, not traffic consent or
        a successful test. Actual agent invocations can each make multiple model
        or tool calls; these are not model-call/token/spend quotas. Actually
        executing explicit evaluation can make judge-provider calls, but judges
        consume captured answers and must never reinvoke the agent.
    """
    if evaluation not in {"off", "explicit"}:
        raise ValueError("This sample supports evaluation off or explicit; no automatic planner")
    if sample_refund_policy and (evaluation != "explicit" or case is not None):
        raise ValueError(
            "Use the confirmed sample policy only for explicit evaluation without a custom case"
        )
    if case is None:
        if evaluation == "explicit" and not sample_refund_policy:
            raise ValueError(
                "Provide authoritative Case.reference or confirm the sample refund policy"
            )
        case = Case(
            input={"query": SAMPLE_QUERY},
            reference={"expected_facts": [SAMPLE_REFERENCE]} if sample_refund_policy else {},
        )
    else:
        # Detach mutable caller dictionaries without executing scorers/providers.
        case = Case.model_validate(case.model_dump(mode="json"))
    reference_response = case.reference.get("expected_response")
    reference_facts = case.reference.get("expected_facts")
    has_reference = (isinstance(reference_response, str) and bool(reference_response.strip())) or (
        isinstance(reference_facts, list)
        and bool(reference_facts)
        and all(isinstance(fact, str) and fact.strip() for fact in reference_facts)
    )
    if evaluation == "explicit" and not has_reference:
        raise ValueError(
            "Explicit correctness requires authoritative expected_response or expected_facts in Case.reference"
        )
    policy = (
        EvaluationPolicy(
            mode="explicit",
            description="Judge relevance and correctness against the caller-authorized case reference.",
            scorers=["relevance", "correctness"],
            max_scored_requests=1,
        )
        if evaluation == "explicit"
        else EvaluationPolicy()
    )
    return RunCreate(
        name=journey.id,
        target=TargetReference(connection_id="agent"),
        cases=[case],
        load=Load(concurrency=1, duration_seconds=10, max_requests=1, timeout_seconds=40),
        evaluation=policy,
    )


def binding(
    journey: Journey,
    *,
    http_url: str | None = None,
    app_name: str | None = None,
    profile: str | None = None,
    bearer_token_env: str | None = None,
) -> Agent:
    """Validate an exact operator-owned target, without discovery or credentials.

    Args:
        journey: Selected runner/hosting/framework labels.
        http_url: Exact approved HTTP agent endpoint using the http-json contract.
            Cloud runners require a reachable HTTPS endpoint, not laptop loopback.
        app_name: Exact deployed agent App name, separate from a runner App name.
        profile: Explicit SDK profile available to the eventual owner and worker.
            Cloud OAuth readiness and permissions remain independent live gates.
        bearer_token_env: Optional operator-owned environment-variable name for
            HTTP bearer authentication. Never a token value. Requires HTTPS even
            for loopback and is rejected for an App target. Construction does not
            read it; the existing worker resolves its value at dispatch time.

    Returns:
        An inert public SDK target binding, kept outside benchmark requests.

    Raises:
        ValueError: Missing/mixed configuration, invalid endpoint, or a loopback
            or non-HTTPS destination selected from a cloud runner. No DNS resolution occurs;
            syntactic acceptance does not prove routing, auth, or inference.
    """
    if journey.hosting == "databricks-app":
        if bearer_token_env is not None:
            raise ValueError("App targets reject HTTP bearer environment references")
        if http_url is not None or not app_name or not profile:
            raise ValueError("An App target requires only an exact App name and explicit profile")
        return Agent.databricks_app(app_name, profile=profile)
    if not http_url or app_name is not None or profile is not None:
        raise ValueError("An HTTP target requires only its exact approved endpoint")
    if bearer_token_env is not None and (
        not isinstance(bearer_token_env, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,255}", bearer_token_env) is None
    ):
        raise ValueError("Select a bearer environment-variable name, never a token value")
    endpoint = urlsplit(http_url)
    if bearer_token_env is not None and endpoint.scheme != "https":
        raise ValueError("Bearer authentication requires HTTPS, including loopback")
    host = endpoint.hostname
    if not host:
        raise ValueError("Select an exact HTTP endpoint with a host")
    host = host.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        loopback = host == "localhost" or host.endswith(".localhost")
    else:
        loopback = address.is_loopback or address.is_unspecified
    if journey.runner != "local" and loopback:
        raise ValueError(
            "Cloud runners cannot reach a laptop localhost agent; select an approved reachable HTTPS endpoint"
        )
    if journey.runner != "local" and endpoint.scheme != "https":
        raise ValueError("Cloud HTTP targets require HTTPS at an approved reachable endpoint")
    return Agent.http(
        http_url,
        protocol="http-json",
        connection=Connection(
            url=http_url,
            auth="bearer" if bearer_token_env is not None else "none",
            token_env=bearer_token_env,
        ),
    )


def main() -> None:
    """Print logical inventory or schema-valid request JSON; never execute traffic.

    Side Effects:
        Writes labels/schema JSON to stdout, with no selected profile, credential,
        URL, auth call, worker, model call, or cloud mutation. The request command
        checks an operator binding statically and deliberately does not run it.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("matrix", help="List fifteen requested cells; none are live results")
    selected = commands.add_parser("request", help="Validate configuration, print workload only")
    selected.add_argument("--framework", required=True, choices=FRAMEWORKS)
    selected.add_argument("--runner", required=True, choices=RUNNERS)
    selected.add_argument("--hosting", required=True, choices=TARGETS)
    selected.add_argument("--http-url")
    selected.add_argument("--app-name")
    selected.add_argument("--profile")
    selected.add_argument(
        "--bearer-token-env",
        help="HTTP-only operator environment-variable name; HTTPS required, never a token value",
    )
    selected.add_argument("--evaluation", choices=("off", "explicit"), default="off")
    selected.add_argument(
        "--sample-refund-policy",
        action="store_true",
        help="Affirm this target implements the exact real_framework_agent.py synthetic policy",
    )
    selected.add_argument(
        "--query", help="Caller-owned case input, without changing target configuration"
    )
    selected.add_argument(
        "--reference-fact",
        action="append",
        help="Authoritative expected fact for correctness; repeat for multiple facts",
    )
    options = parser.parse_args()
    if options.command == "matrix":
        print(
            json.dumps(
                {
                    "validation": "logical-inventory-only",
                    "serverless_scope": "deployed-app-targets-only",
                    "retained_optional_sample": "serverless-http-outside-requested-validation",
                    "journeys": [
                        {
                            "id": item.id,
                            "framework": item.framework,
                            "runner": item.runner,
                            "target_hosting": item.hosting,
                            "fresh_live_validation": "not_run",
                            "http_reachability": "approved-reachable-https-required"
                            if item.runner == "databricks-app" and item.hosting == "http"
                            else "not-applicable",
                        }
                        for item in journeys()
                    ],
                },
                indent=2,
            )
        )
        return
    try:
        journey = Journey(options.framework, options.runner, options.hosting)
        binding(
            journey,
            http_url=options.http_url,
            app_name=options.app_name,
            profile=options.profile,
            bearer_token_env=options.bearer_token_env,
        )
        custom_case = (
            Case(
                input={"query": options.query if options.query is not None else SAMPLE_QUERY},
                reference={"expected_facts": options.reference_fact}
                if options.reference_fact
                else {},
            )
            if options.query is not None or options.reference_fact is not None
            else None
        )
        workload = request(
            journey,
            evaluation=options.evaluation,
            case=custom_case,
            sample_refund_policy=options.sample_refund_policy,
        )
    except ValueError:
        # Native schema/URL errors can include supplied credential-bearing inputs.
        parser.error(
            "Review exact target selection, reachable HTTPS URL, bearer environment-variable "
            "name, evaluation policy, and authoritative references or confirmed sample refund policy. "
            "Requested serverless notebook validation targets deployed Apps only."
        )
    print(workload.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
