# Databricks notebook source
# MAGIC %md
# MAGIC # Serverless load generator -> deployed agent App (portable OAuth gate)
# MAGIC This notebook runs EvalSurge/Locust only. The customer agent and real model
# MAGIC calls remain inside an already deployed Databricks App. It never hosts an
# MAGIC EvalSurge API server or agent/helper, creates a service principal,
# MAGIC copies a notebook token to a worker,
# MAGIC or falls back to classic compute. Install the reviewed current wheel in an
# MAGIC explicitly selected serverless environment separately before running.
# MAGIC
# MAGIC **Authentication:** supply an already provisioned, private local profile file
# MAGIC using `auth_type = oauth-m2m` and the explicitly selected service-principal
# MAGIC client ID. Credentials stay outside benchmark requests. The notebook launches
# MAGIC an isolated EvalSurge owner; normal Locust workers independently refresh OAuth.
# MAGIC The existing conflicting-selector guards remain active. Native notebook tokens,
# MAGIC copied laptop profiles/caches, PATs and automatic identity/secret creation are
# MAGIC not supported by this sample. See proposed ADR 0015 and SERVERLESS_RUNNER_STATUS.
# MAGIC
# MAGIC **Current gate:** no portable identity/credential source or live notebook-to-App
# MAGIC pass has yet been established: this is not proven live notebook-to-App support.
# MAGIC Maintainer design review and explicit resource /
# MAGIC bounded traffic approval remain required. Dry-run makes no auth/model calls.
# MAGIC
# MAGIC Initial traffic must select one reviewed no-tool App with a <=512 output-token
# MAGIC limit and allow at most one preflight plus one measured invocation.
# MAGIC Fail-fast and cancellation need separate reviewed leases;
# MAGIC this initial direct-run gate does not claim their notebook coverage.
# MAGIC Run `check_authentication_only=true` first with explicit metadata/token-access
# MAGIC approval. It performs zero target/model calls and does not label the journey
# MAGIC passed. Then a separately approved paid smoke can enable `allow_paid_inference`.
# MAGIC
# MAGIC **Installation prerequisite—not yet tested on serverless:** install the exact
# MAGIC reviewed wheel **and** its `[server]` direct-runtime dependencies. The documented
# MAGIC Environment wheel picker alone does not establish optional-extra installation.
# MAGIC Prepare a reviewed requirements file containing the exact authorized path,
# MAGIC for example `/Volumes/.../evalsurge-<reviewed-version>-py3-none-any.whl[server]`;
# MAGIC in the Environment side pane add `-r /Workspace/.../evalsurge-requirements.txt`.
# MAGIC The side pane accepts requirements-file syntax; `[server]` is pip's optional
# MAGIC dependency syntax, not a request to host an EvalSurge API server. Configure
# MAGIC the approved package index there and click Apply. This recipe is source-backed,
# MAGIC not live install evidence. Applying dependencies restarts Python: run these
# MAGIC cells only afterward. The installed wheel includes
# MAGIC `evalsurge.serverless`; no repository checkout or `source_root` widget is needed.
# MAGIC Use a new reviewed package version after source changes, not an overwritten
# MAGIC same-version artifact. Native dependencies must support the runtime architecture.
# MAGIC A protected credential file is a separate operator prerequisite, never a
# MAGIC notebook dependency, a widget secret, or something this sample provisions.
# MAGIC Select the same wheel path, reviewed SHA256 and exact distribution version
# MAGIC below. Artifact/version checks run before OAuth or model calls. They verify
# MAGIC the selected artifact and active installation version, not that notebook
# MAGIC credentials are usable or that dependencies/install execution succeeded here.
# MAGIC This is a prepared example, not a recorded successful serverless benchmark.
# MAGIC
# MAGIC Installation source: [Configure the serverless environment]
# MAGIC (https://docs.databricks.com/aws/en/compute/serverless/dependencies).
# MAGIC [Notebook App token exchange]
# MAGIC (https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local)
# MAGIC enables direct API calls but is not evidence of the independently refreshable
# MAGIC Locust worker credentials required by this sample; it is not substituted here.

# COMMAND ----------

import hashlib
import json
import re
import tempfile
from importlib.metadata import version
from pathlib import Path

from evalsurge.serverless import budget_record, launch_runner_async, parse_options

dbutils.widgets.text("reviewed_wheel", "")  # noqa: F821
dbutils.widgets.text("reviewed_sha256", "")  # noqa: F821
dbutils.widgets.text("reviewed_version", "")  # noqa: F821
dbutils.widgets.text("workspace", "")  # noqa: F821
dbutils.widgets.text("app_name", "")  # noqa: F821
dbutils.widgets.text("profile", "")  # noqa: F821
dbutils.widgets.text("oauth_config_file", "")  # noqa: F821
dbutils.widgets.text("oauth_client_id", "")  # noqa: F821
dbutils.widgets.text("target_model", "")  # noqa: F821
dbutils.widgets.text("source_revision", "")  # noqa: F821
dbutils.widgets.dropdown("allow_paid_inference", "false", ["false", "true"])  # noqa: F821
dbutils.widgets.dropdown("check_authentication_only", "false", ["false", "true"])  # noqa: F821

# COMMAND ----------


def verify_reviewed_install(wheel: str, expected_sha256: str, expected_version: str) -> None:
    """Check operator-selected artifact/version before authentication or traffic.

    Args:
        wheel: Exact readable reviewed wheel in Workspace Files or a UC Volume.
        expected_sha256: Separately reviewed artifact's lowercase SHA256.
        expected_version: Exact reviewed installed distribution version.

    Raises:
        ValueError: Selection, artifact digest, or active version does not match.
        OSError: The selected artifact is not readable in this notebook environment.

    Side Effects:
        Streams local artifact bytes and reads installed metadata; no auth, agent,
        network, install or deployment calls. Matching metadata is not independent
        proof that every installed dependency matches the reviewed environment.
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


verify_reviewed_install(
    dbutils.widgets.get("reviewed_wheel"),  # noqa: F821
    dbutils.widgets.get("reviewed_sha256"),  # noqa: F821
    dbutils.widgets.get("reviewed_version"),  # noqa: F821
)

arguments = []
for name in (
    "workspace",
    "app_name",
    "profile",
    "target_model",
    "source_revision",
):
    arguments.extend(["--" + name.replace("_", "-"), dbutils.widgets.get(name)])  # noqa: F821
for name in ("oauth_config_file", "oauth_client_id"):
    value = dbutils.widgets.get(name)  # noqa: F821
    if value:
        arguments.extend(["--" + name.replace("_", "-"), value])
consent = dbutils.widgets.get("allow_paid_inference") == "true"  # noqa: F821
check_authentication = dbutils.widgets.get("check_authentication_only") == "true"  # noqa: F821
if check_authentication:
    arguments.append("--check-authentication")
if consent:
    arguments.extend(
        [
            "--live",
            "--accept-paid-traffic",
            "--real-inference-attested",
            "--artifact-dir",
            tempfile.mkdtemp(prefix="evalsurge-serverless-app-target-"),
        ]
    )
options = parse_options(arguments)
if not (consent or check_authentication):
    dbutils.notebook.exit(json.dumps(budget_record(options), sort_keys=True))  # noqa: F821

# COMMAND ----------

receipt = await launch_runner_async(options)  # noqa: F704
dbutils.notebook.exit(json.dumps(receipt, sort_keys=True))  # noqa: F821
