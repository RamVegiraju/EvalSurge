"""Runner: local Python/laptop. Target: a separately hosted real HTTP agent.

EvalSurge generates load; it never imports or hosts the customer's agent. Start
the agent separately and select its exact reachable endpoint. The default is the
minimal nonstreaming http-json contract. This file does not run on a notebook.
"""

import argparse
import re
from typing import Literal
from urllib.parse import urlsplit

from evalsurge import (
    Agent,
    Case,
    Connection,
    EvalSurge,
    Load,
    RunCreate,
    TargetReference,
    format_summary,
)


def binding(
    url: str,
    *,
    protocol: Literal["http-json", "openai-chat", "mlflow-agent-server"] = "http-json",
    bearer_token_env: str | None = None,
) -> Agent:
    """Construct an exact HTTP binding without reading secrets or making calls.

    Args:
        url: Operator-approved agent endpoint, separate from the runner process.
        protocol: Explicit endpoint contract; framework names do not select it.
        bearer_token_env: Optional environment-variable name, never a token value.
            The existing worker resolves its value at dispatch; select/provision
            the operator credential outside requests before running this example.

    Returns:
        An inert target/connection pair kept outside the benchmark request.

    Raises:
        ValueError: The endpoint/protocol/reference is invalid, or a bearer target
            does not use HTTPS. Unauthenticated loopback HTTP remains supported.

    Side Effects:
        None. This validates configuration, not authentication, consent or inference.
    """
    if bearer_token_env is not None and (
        not isinstance(bearer_token_env, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,255}", bearer_token_env) is None
    ):
        raise ValueError("Select a bearer environment-variable name, never a token value")
    if bearer_token_env is not None and urlsplit(url).scheme != "https":
        raise ValueError("Bearer authentication requires HTTPS, including loopback")
    return Agent.http(
        url,
        protocol=protocol,
        connection=Connection(
            url=url,
            auth="bearer" if bearer_token_env is not None else "none",
            token_env=bearer_token_env,
        ),
    )


def request() -> RunCreate:
    """Build a five-attempt load-only smoke; construction makes no network calls."""
    return RunCreate(
        name="local-runner-http-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(concurrency=5, duration_seconds=10, max_requests=5, timeout_seconds=40),
    )


def main() -> None:
    """Run from this machine against the selected customer-owned HTTP endpoint.

    Side Effects:
        Owns one local Locust worker and protected artifacts. Up to five measured
        invocations plus one excluded probe may incur actual model/tool costs.
        Evaluation is off; no planner or judge calls. This is a functional smoke,
        not sustainable-capacity evidence or a model-call/token/spend quota.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Exact authorized endpoint of the existing real agent")
    parser.add_argument(
        "--protocol",
        choices=("http-json", "openai-chat", "mlflow-agent-server"),
        default="http-json",
    )
    parser.add_argument("--allow-paid-inference", action="store_true")
    parser.add_argument(
        "--bearer-token-env",
        help="Operator environment-variable name for HTTPS bearer auth, never a token value",
    )
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review six possible agent invocations; pass --allow-paid-inference.")
    try:
        agent = binding(args.url, protocol=args.protocol, bearer_token_env=args.bearer_token_env)
    except ValueError:
        parser.error("Review the exact endpoint, protocol and bearer environment-variable name.")
    with EvalSurge(
        artifact_dir="artifacts/local-runner-http-target",
        targets={"agent": agent},
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(format_summary(report))


if __name__ == "__main__":
    main()
