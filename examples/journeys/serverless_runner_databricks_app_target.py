# Databricks notebook source
# MAGIC %md
# MAGIC # Review-only: serverless load generator -> deployed agent App
# MAGIC This notebook runs EvalSurge/Locust only. The customer agent and real model
# MAGIC calls remain inside an already deployed Databricks App. It never hosts an
# MAGIC agent/helper, creates a service principal, copies a notebook token to a worker,
# MAGIC or falls back to classic compute. Install the reviewed current wheel in an
# MAGIC explicitly selected serverless environment separately before running.
# MAGIC
# MAGIC **Current gate:** App binding is profile-only and rejects notebook ambient
# MAGIC identity/destination overrides; native driver runtime-OAuth is unavailable to
# MAGIC the independent Locust worker. A laptop profile name is not portable notebook
# MAGIC authentication. Resolve a supported operator-owned OAuth design through ADR
# MAGIC and maintainer review before authorizing a live Job. This is not proven live
# MAGIC notebook-to-App support. Dry-run outputs only fixed bounds and makes no calls.
# MAGIC
# MAGIC Initial traffic must select one reviewed no-tool App with a <=512 output-token
# MAGIC limit and allow at most one preflight plus one measured invocation. Optional
# MAGIC REST/API execution, fail-fast and cancellation need separate reviewed leases;
# MAGIC this initial direct-run gate does not claim their notebook coverage.

# COMMAND ----------

import json
import sys
import tempfile
from pathlib import Path

dbutils.widgets.text("source_root", "")  # noqa: F821
dbutils.widgets.text("workspace", "")  # noqa: F821
dbutils.widgets.text("app_name", "")  # noqa: F821
dbutils.widgets.text("profile", "")  # noqa: F821
dbutils.widgets.text("target_model", "")  # noqa: F821
dbutils.widgets.text("source_revision", "")  # noqa: F821
dbutils.widgets.dropdown("allow_paid_inference", "false", ["false", "true"])  # noqa: F821

# COMMAND ----------

source_root = Path(dbutils.widgets.get("source_root")).resolve()  # noqa: F821
if not str(source_root).startswith("/Workspace/Users/") or not source_root.is_dir():
    raise ValueError("Select the exact reviewed user-owned validation source directory")
sys.path.insert(0, str(source_root))

from scripts.validation.serverless_runner_app_target import (  # noqa: E402
    budget_record,
    execute,
    parse_options,
)

arguments = []
for name in ("workspace", "app_name", "profile", "target_model", "source_revision"):
    arguments.extend(["--" + name.replace("_", "-"), dbutils.widgets.get(name)])  # noqa: F821
consent = dbutils.widgets.get("allow_paid_inference") == "true"  # noqa: F821
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
if not consent:
    dbutils.notebook.exit(json.dumps(budget_record(options), sort_keys=True))  # noqa: F821

# COMMAND ----------

receipt = await execute(options)  # noqa: F704 - notebook supports top-level await
dbutils.notebook.exit(json.dumps(receipt, sort_keys=True))  # noqa: F821
