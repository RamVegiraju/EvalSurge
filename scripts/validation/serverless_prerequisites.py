# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
"""Credential-free, zero-inference notebook prerequisite checks.

Import as a SOURCE notebook and pass the approved HTTPS workspace origin in the
``workspace`` widget. This makes authentication/identity reads, never inference.
It tests native driver and independent subprocess OAuth; success of the notebook
task alone is not success of every check. Output contains booleans/error classes,
not tokens, headers, provider messages, or raw authentication exceptions.
"""

import fcntl
import json
import os
import socket
import subprocess
import sys
import tempfile
from importlib.metadata import version
from urllib.parse import urlsplit

from databricks.sdk import WorkspaceClient

dbutils.widgets.text("workspace", "")  # noqa: F821 - Databricks source notebook
expected_host = dbutils.widgets.get("workspace").rstrip("/")  # noqa: F821
parsed = urlsplit(expected_host)
if (
    parsed.scheme != "https"
    or not parsed.hostname
    or parsed.username
    or parsed.password
    or parsed.path
    or parsed.query
    or parsed.fragment
    or parsed.port not in {None, 443}
):
    raise ValueError("An explicitly approved HTTPS workspace origin is required")

checks = {
    "inference_calls": 0,
    "python_version": sys.version.split()[0],
    "databricks_sdk_version": version("databricks-sdk"),
    "databricks_env_names": sorted(k for k in os.environ if k.startswith("DATABRICKS_")),
    "deployed_app_tested": False,
}
for auth_type in ("runtime", "runtime-oauth"):
    result = {}
    try:
        workspace = WorkspaceClient(host=expected_host, auth_type=auth_type, scopes=["all-apis"])
        result["workspace_matches"] = workspace.config.host.rstrip("/") == expected_host
        if not result["workspace_matches"]:
            raise ValueError
        result["current_user_active"] = workspace.current_user.me().active
        try:
            result["oauth_available"] = bool(workspace.config.oauth_token().access_token)
        except Exception as error:  # noqa: BLE001 - never export authentication messages
            result["oauth_available"] = False
            result["oauth_error_type"] = type(error).__name__
    except Exception as error:  # noqa: BLE001 - only fixed types, no credentials
        result["error_type"] = type(error).__name__
    checks[auth_type] = result

try:
    with (
        tempfile.TemporaryDirectory(prefix="evalsurge-prerequisites-") as directory,
        open(os.path.join(directory, "owner.lock"), "w") as lock,
    ):
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.write("owned")
        lock.flush()
        os.fsync(lock.fileno())
        checks["posix_lock_fsync"] = True
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with socket.create_connection(listener.getsockname(), timeout=2), listener.accept()[0]:
            checks["loopback_socket"] = True
except Exception as error:  # noqa: BLE001 - no system details in safe output
    checks["local_resource_error_type"] = type(error).__name__

try:
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json\n"
            "from databricks.sdk import WorkspaceClient\n"
            "try:\n"
            f" w=WorkspaceClient(host={expected_host!r},auth_type='runtime-oauth',scopes=['all-apis'])\n"
            f" assert w.config.host.rstrip('/') == {expected_host!r}\n"
            " print(json.dumps({'auth_type':w.config.auth_type,"
            "'oauth_available':bool(w.config.oauth_token().access_token)}))\n"
            "except Exception as e:\n"
            " print(json.dumps({'error_type':type(e).__name__}))\n",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    checks["subprocess_returncode"] = child.returncode
    checks["subprocess_auth"] = json.loads(child.stdout.splitlines()[-1])
except Exception as error:  # noqa: BLE001 - no captured stdout/stderr is exported
    checks["subprocess_auth"] = {"error_type": type(error).__name__}

dbutils.notebook.exit(json.dumps(checks, sort_keys=True))  # noqa: F821
