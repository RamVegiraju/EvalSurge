"""Runner: private Databricks App. Agent target: a separate HTTP endpoint or App.

There is no EvalSurge REST benchmark service here. The HTTP surface is static
health and content-free status only. Default deployment performs no model calls.
"""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI

try:
    from .runner import read_config, run_once
except ImportError:  # App deployment runs this standalone directory, not a package.
    from runner import read_config, run_once

ROOT = Path(__file__).resolve().parent
STATUS: dict[str, str | bool] = {
    "state": "disabled",
    "passed": False,
    "benchmark_passed": False,
    "approval_consumed_observed": False,
    "protected_export_ready": False,
    "export_status": "not_started",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Own exactly one optional direct-run task and await it during App shutdown.

    Side Effects:
        Reads fixed local operator JSON. Only explicit fresh live consent can
        start SDK/network work; the disabled template performs none. Cancelling
        the App stops dispatch and awaits owned cleanup, subject to platform
        termination grace. No success is inferred from process termination.
    """
    task: asyncio.Task[None] | None = None
    try:
        config = read_config(
            Path(os.environ.get("EVALSURGE_OPERATOR_CONFIG", ROOT / "operator.example.json"))
        )
        if config.enabled:
            task = asyncio.create_task(run_once(config, ROOT, STATUS))
    except ValueError:
        STATUS["state"] = "configuration_blocked"
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            with suppress(asyncio.CancelledError):
                task.result()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
def health() -> dict[str, str]:
    """Return static health, not permission/auth/inference/generator readiness."""
    return {"service": "private-evalsurge-direct-runner", "health": "up"}


@app.get("/status")
def status() -> dict[str, str | bool]:
    """Return content-free lifecycle flags; never targets, reports or credentials."""
    return dict(STATUS)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")),
        workers=1,
        timeout_graceful_shutdown=10,
        access_log=False,
    )
