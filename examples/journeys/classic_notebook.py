# Databricks notebook source
# MAGIC %md
# MAGIC # Direct App benchmark: classic compute first
# MAGIC Attach this notebook to an explicitly selected classic cluster.
# MAGIC Install your reviewed EvalSurge wheel with the `server` extra and restart
# MAGIC Python before this cell. Configure a user-selected OAuth profile on the
# MAGIC driver; your laptop's profile does not transfer here. Ensure the CLI/SDK
# MAGIC credential mechanism is also available to spawned Python workers.
# MAGIC Do not paste tokens into notebook source. This sample does not deploy Apps,
# MAGIC create compute, install authentication, or demonstrate serverless support.
# MAGIC Run the widget and execution cells together; do not leave an open client
# MAGIC in notebook globals across cells. Local driver artifacts are not durable
# MAGIC evidence across cluster termination; export them privately if needed.

# COMMAND ----------

from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

dbutils.widgets.text("app_name", "")  # noqa: F821
dbutils.widgets.text("oauth_profile", "")  # noqa: F821
dbutils.widgets.dropdown("allow_paid_inference", "false", ["false", "true"])  # noqa: F821

# COMMAND ----------

app_name = dbutils.widgets.get("app_name").strip()  # noqa: F821
profile = dbutils.widgets.get("oauth_profile").strip()  # noqa: F821
consent = dbutils.widgets.get("allow_paid_inference") == "true"  # noqa: F821
if not app_name or not profile or not consent:
    raise ValueError("Select the deployed App and explicit OAuth profile; approve paid traffic.")

request = RunCreate(
    name="classic-notebook-app-baseline",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=5, duration_seconds=30, max_requests=10, timeout_seconds=60),
)

# The context releases ownership after success, failure, or interruption. It can
# wait for active requests to drain; stopping a notebook is not immediate cancel.
# This is ten measured App invocations at most plus one excluded probe. Each can
# perform multiple model/tool calls; this is not a model-call/token/spend quota.
# Quality is off. Traffic requires the consent widget explicitly set to true.
with EvalSurge(
    artifact_dir="/local_disk0/tmp/evalsurge-classic-app",
    targets={"agent": Agent.databricks_app(app_name, profile=profile)},
) as client:
    run = client.start(request)
    report = run.wait(timeout=300)
    print(report.model_dump_json(indent=2))

# COMMAND ----------
# MAGIC %md
# MAGIC Review phases and evidence gaps, not only lifecycle completion.
# MAGIC To request cancellation during preflight/load in a coordinated lifecycle,
# MAGIC use `run.cancel()` then wait for drain before closing its owning client.
# MAGIC A wait timeout alone does not cancel. Do not terminate shared compute as
# MAGIC cleanup. Verify this notebook with real inference on classic compute
# MAGIC before performing a separate consented serverless validation.
