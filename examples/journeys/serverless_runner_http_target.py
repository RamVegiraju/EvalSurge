# Databricks notebook source
# MAGIC %md
# MAGIC # Serverless load generator -> separately hosted real HTTP agent
# MAGIC **Installation prerequisite—not yet tested on serverless:** install the exact
# MAGIC reviewed wheel **and** its `[server]` direct-runtime dependencies. The documented
# MAGIC Environment wheel picker alone does not establish optional-extra installation.
# MAGIC Prepare a reviewed requirements file containing the exact authorized path,
# MAGIC for example `/Volumes/.../evalsurge-<reviewed-version>-py3-none-any.whl[server]`;
# MAGIC in the Environment side pane add `-r /Workspace/.../evalsurge-requirements.txt`.
# MAGIC The side pane accepts requirements-file syntax; `[server]` is pip's optional
# MAGIC dependency syntax, not a request to host an EvalSurge API server. Configure
# MAGIC the approved package index in that environment, click Apply, and rerun after
# MAGIC Python restarts. This recipe is source-backed, not live install evidence. Do not
# MAGIC install PySpark or assume a public `evalsurge` release exists. This notebook
# MAGIC needs the installed package only, not a checkout, `examples` imports or an
# MAGIC EvalSurge API server. Use a new reviewed version after source changes.
# MAGIC
# MAGIC The agent may use CrewAI, LangGraph, OpenAI Agents or any other framework;
# MAGIC it runs separately and must make real model calls. This notebook generates
# MAGIC load using the normal Locust subprocess; it does not host/import the agent.
# MAGIC Select an exact authorized HTTPS endpoint reachable from serverless compute.
# MAGIC `localhost` in this notebook is the notebook, not your laptop: a laptop-only
# MAGIC agent cannot be reached through its loopback address from Databricks.
# MAGIC Do not open a tunnel, change network policy or make the endpoint public just
# MAGIC to run this example. Have its operator provide approved network/auth access.
# MAGIC
# MAGIC Default wire contract: `http-json`, with input `{"query": "..."}` and a
# MAGIC nonempty completed answer in `{"outputs": "..."}`. Select an explicit
# MAGIC supported protocol only if the target already implements that contract.
# MAGIC Optional bearer authentication is an operator-owned environment-variable
# MAGIC reference, never a token widget or benchmark request field. Provision it
# MAGIC securely before this notebook; this sample never creates/copies credentials.
# MAGIC
# MAGIC **Traffic:** concurrency one, at most one measured invocation plus one
# MAGIC excluded inference preflight, evaluation off. Model/tool calls inside each
# MAGIC invocation are agent-owned: review the deployed model/output/tool limits and
# MAGIC approve a separate spend bound. This is a functional smoke, not capacity or
# MAGIC zero-overhead evidence. Explicit/automatic evaluation requires separately
# MAGIC approved planner/judge configuration and is not validated by this load-only
# MAGIC sample. Never substitute canned answers to make an inference test pass.
# MAGIC
# MAGIC **Status:** prepared, not live-validated on serverless. Artifact/version,
# MAGIC syntax and schema checks do not establish installation, network, real-model,
# MAGIC notebook cleanup or successful load/evaluation coverage there. Keep failed
# MAGIC artifacts. Export evidence privately before notebook/environment termination;
# MAGIC notebook-local storage is not durable. Context closure cancels dispatch and
# MAGIC drains owned work, but cannot undo already dispatched model/tool calls.
# MAGIC
# MAGIC Installation source: [Configure the serverless environment]
# MAGIC (https://docs.databricks.com/aws/en/compute/serverless/dependencies).
# MAGIC Serverless can use x86_64 or aarch64: confirm native transitive dependencies
# MAGIC support the selected environment, not just EvalSurge's pure-Python wheel.

# COMMAND ----------

import hashlib
import ipaddress
import re
import tempfile
from contextlib import suppress
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

from evalsurge import (
    Agent,
    Case,
    Connection,
    EvalSurge,
    Load,
    Report,
    RunCreate,
    RunFailed,
    TargetReference,
    format_summary,
)

dbutils.widgets.text("reviewed_wheel", "")  # noqa: F821
dbutils.widgets.text("reviewed_sha256", "")  # noqa: F821
dbutils.widgets.text("reviewed_version", "")  # noqa: F821
dbutils.widgets.text("target_url", "")  # noqa: F821
dbutils.widgets.text("target_model", "")  # noqa: F821
dbutils.widgets.text("target_source_revision", "")  # noqa: F821
dbutils.widgets.text("bearer_token_env", "")  # noqa: F821
dbutils.widgets.dropdown(  # noqa: F821
    "protocol", "http-json", ["http-json", "openai-chat", "mlflow-agent-server"]
)
dbutils.widgets.dropdown("allow_paid_inference", "false", ["false", "true"])  # noqa: F821

# COMMAND ----------


def verify_reviewed_install(wheel: str, expected_sha256: str, expected_version: str) -> None:
    """Check the reviewed artifact and active version without traffic/install calls.

    Args:
        wheel: Exact readable reviewed wheel in Workspace Files or a UC Volume.
        expected_sha256: Separately reviewed artifact's lowercase SHA256.
        expected_version: Exact reviewed installed distribution version.

    Raises:
        ValueError: Selection, artifact digest, or active version does not match.
        OSError: The selected artifact cannot be read from this environment.

    Side Effects:
        Streams local wheel bytes and reads installed distribution metadata. A
        match does not prove installation/dependency execution on serverless.
    """
    path = Path(wheel)
    if (
        not path.is_absolute()
        or not wheel.startswith(("/Workspace/", "/Volumes/"))
        or path.suffix != ".whl"
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or not expected_version.strip()
    ):
        raise ValueError("Select the reviewed wheel, exact SHA256 and installed version.")
    with path.open("rb") as artifact:
        observed = hashlib.file_digest(artifact, "sha256").hexdigest()
    if observed != expected_sha256 or version("evalsurge") != expected_version:
        raise ValueError("Reviewed artifact or active EvalSurge version does not match.")


def validate_notebook_target(url: str) -> None:
    """Reject notebook-loopback/bind-address mistakes without DNS or HTTP calls.

    Args:
        url: Operator-selected endpoint of the separately hosted agent.

    Raises:
        ValueError: The URL is not HTTPS or names loopback/an unspecified bind address.

    Side Effects:
        None. Network reachability, ownership, authentication and inference are
        separate live gates; this is not an egress/security-policy validator.
    """
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    loopback = hostname == "localhost" or hostname.endswith(".localhost")
    with suppress(ValueError):
        address = ipaddress.ip_address(hostname)
        loopback = loopback or address.is_loopback or address.is_unspecified
    # Hostnames remain subject to operator network policy and live readiness.
    if parsed.scheme != "https" or not hostname or loopback:
        raise ValueError("Select an authorized HTTPS agent endpoint reachable from serverless.")


verify_reviewed_install(
    dbutils.widgets.get("reviewed_wheel"),  # noqa: F821
    dbutils.widgets.get("reviewed_sha256"),  # noqa: F821
    dbutils.widgets.get("reviewed_version"),  # noqa: F821
)
target_url = dbutils.widgets.get("target_url").strip()  # noqa: F821
target_model = dbutils.widgets.get("target_model").strip()  # noqa: F821
target_revision = dbutils.widgets.get("target_source_revision").strip()  # noqa: F821
validate_notebook_target(target_url)
if not target_model or not target_revision:
    raise ValueError("Record the actual target model and source revision before testing.")
if dbutils.widgets.get("allow_paid_inference") != "true":  # noqa: F821
    raise ValueError("Review two possible real-agent invocations and explicitly approve traffic.")

token_env = dbutils.widgets.get("bearer_token_env").strip()  # noqa: F821
connection = Connection(
    url=target_url,
    auth="bearer" if token_env else "none",
    token_env=token_env or None,
)
agent = Agent.http(
    target_url,
    protocol=dbutils.widgets.get("protocol"),  # noqa: F821
    model=target_model,
    connection=connection,
)
request = RunCreate(
    name="serverless-runner-http-target-smoke",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=1, duration_seconds=5, max_requests=1, timeout_seconds=40),
)

# COMMAND ----------

# One context in one execution cell: do not leave an owning client open between
# cells. Native async uses the notebook loop without nesting asyncio.run(). The
# usual Locust process generates load here, not at a separate API service.


async def run_benchmark(agent: Agent, request: RunCreate, artifact_dir: Path) -> Report:
    """Generate notebook-owned load and retrieve the preserved typed report.

    Args:
        agent: Operator-authorized real HTTP target, already bound outside request.
        request: One measured attempt with evaluation off and an excluded preflight.
        artifact_dir: New private, notebook-local directory owned by this client.

    Returns:
        Typed report, including recorded failed runs. Raw evidence remains private.

    Raises:
        TimeoutError: The 180-second waiter expires; context exit then drains work.
        RuntimeError: Retrieved status/result/report identities disagree.

    Side Effects:
        Runs the normal Locust subprocess, up to two real target invocations, and
        protected storage. Prints only the content-free summary. Context closure
        stops dispatch and drains work; it cannot roll back remote side effects.
        Do not kill shared compute to stop this one owner's worker.
    """
    async with EvalSurge.local_async(
        artifact_dir=artifact_dir,
        targets={"agent": agent},
    ) as client:
        run = await client.start(request)
        try:
            report = await run.wait(timeout=180)
        except RunFailed as error:
            report = error.report  # Preserve failed phases; no replay or model fallback.
        status = await run.status()
        result = await run.result()
        retrieved = await run.report()
        if not (status.id == result.id == retrieved.run.id == run.id):
            raise RuntimeError("Run/status/result/report identities disagree; retain evidence.")
        print(format_summary(result))
    return report


artifact_dir = Path(tempfile.mkdtemp(prefix="evalsurge-serverless-http-target-"))
report = await run_benchmark(agent, request, artifact_dir)  # noqa: F704

# The context is closed after success/failure/interruption and owns worker drain.
# Retain report/result privately; do not display/export their raw answer evidence
# into notebook logs. Export the artifact directory only to approved private storage.
print("Runner context closed; preserve private artifacts before the notebook terminates.")
