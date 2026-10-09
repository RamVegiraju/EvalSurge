# Databricks notebook source
# MAGIC %md
# MAGIC # Historical diagnostic: notebook-hosted helper (not deployed-App coverage)
# MAGIC Install the reviewed wheel and pinned framework dependencies in a separately
# MAGIC approved serverless environment. The selected source directory contains only
# MAGIC the reviewed validation modules and real-framework handler. This notebook never
# MAGIC imports a laptop profile, uploads tokens, provisions Apps or uses classic compute.
# MAGIC The actual target is a driver-local HTTP helper; optional API execution is an
# MAGIC authenticated driver-local EvalSurge server. Neither is a deployed App test.
# MAGIC Do not use this diagnostic as the intended runner-only notebook sample;
# MAGIC that sample is examples/journeys/serverless_runner_databricks_app_target.py.
# MAGIC Inference is off unless the paid-traffic widget is explicitly true. The returned
# MAGIC JSON receipt's passed field, not Job completion, decides validation success.

# COMMAND ----------

import json
import sys
import tempfile
from pathlib import Path

dbutils.widgets.text("source_root", "")  # noqa: F821
dbutils.widgets.text("workspace", "")  # noqa: F821
dbutils.widgets.text("target_model", "")  # noqa: F821
dbutils.widgets.dropdown("framework", "langgraph", ["langgraph", "openai-agents", "crewai"])  # noqa: F821
dbutils.widgets.dropdown("model_api", "mlflow-responses", ["mlflow-responses", "openai-responses"])  # noqa: F821
dbutils.widgets.dropdown("allow_paid_inference", "false", ["false", "true"])  # noqa: F821
dbutils.widgets.dropdown("exercise_cancel", "false", ["false", "true"])  # noqa: F821

# COMMAND ----------

source_root = Path(dbutils.widgets.get("source_root")).resolve()  # noqa: F821
if not str(source_root).startswith("/Workspace/Users/") or not source_root.is_dir():
    raise ValueError("Select the exact reviewed user-owned workspace source directory")
sys.path.insert(0, str(source_root))

from scripts.validation.serverless_sdk_journeys import (  # noqa: E402
    budget_record,
    execute,
    parse_options,
)

arguments = [
    "--workspace",
    dbutils.widgets.get("workspace"),  # noqa: F821
    "--target-model",
    dbutils.widgets.get("target_model"),  # noqa: F821
    "--framework",
    dbutils.widgets.get("framework"),  # noqa: F821
    "--model-api",
    dbutils.widgets.get("model_api"),  # noqa: F821
    "--concurrency",
    "5",
    "--max-requests",
    "5",
    "--duration",
    "30",
    "--timeout",
    "30",
    "--max-output-tokens",
    "512",
]
if dbutils.widgets.get("exercise_cancel") == "true":  # noqa: F821
    arguments.append("--exercise-cancel")
consent = dbutils.widgets.get("allow_paid_inference") == "true"  # noqa: F821
if consent:
    storage = tempfile.mkdtemp(prefix="evalsurge-serverless-helper-")
    arguments.extend(["--live", "--accept-paid-traffic", "--artifact-dir", storage])
options = parse_options(arguments)
if not consent:
    dbutils.notebook.exit(json.dumps(budget_record(options), sort_keys=True))  # noqa: F821

# COMMAND ----------

receipt = {**budget_record(options), "passed": False}
try:
    receipt = await execute(options)  # noqa: F704 - Databricks notebook supports top-level await
except Exception as error:  # noqa: BLE001 - never return native/provider error messages
    retained = options.artifact_dir / "serverless-journey-validation.json"
    if retained.is_file():
        receipt = json.loads(retained.read_text(encoding="utf-8"))
    receipt["passed"] = False
    receipt["failure_class"] = type(error).__name__
dbutils.notebook.exit(json.dumps(receipt, sort_keys=True))  # noqa: F821
