"""Own native evaluation processes and verify durable evidence, outside load timing."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .configuration import environment
from .models import Plan

MAX_PRIVATE_BYTES = 128 * 1024 * 1024
MAX_CAPTURE_ROWS = 10_000
NATIVE_ENVIRONMENT = {
    "MLFLOW_GENAI_EVAL_MAX_WORKERS": "1",
    "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS": "1",
    "MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false",
    "MLFLOW_USE_BATCH_SPAN_PROCESSOR": "false",
    "MLFLOW_ENABLE_ASYNC_LOGGING": "false",
    "MLFLOW_DISABLE_TELEMETRY": "true",
    "MLFLOW_TRACING_SQL_WAREHOUSE_ID": "",
    "MLFLOW_MODEL_CATALOG_URI": "",
}


def _phase_failure(code: str) -> dict[str, Any]:
    """Return fixed process diagnostics without child exceptions or captured content."""
    diagnostics = {
        "evaluation_worker_cancelled": (
            "The evaluation owner cancelled its worker.",
            "Already dispatched provider calls cannot be undone; inspect the retained phase evidence.",
        ),
        "evaluation_worker_timeout": (
            "The evaluation worker exceeded its separate phase deadline.",
            "Review the frozen sample/retry budgets and operator evaluation deadline before an explicit rerun.",
        ),
        "evaluation_worker_failed": (
            "The native evaluation worker did not return a valid bounded result.",
            "Check the local evaluation store and installed scorer compatibility; load results remain independent.",
        ),
    }
    message, guidance = diagnostics[code]
    return {
        "status": "failed",
        "results": [],
        "error": {"code": code, "message": message, "guidance": guidance},
    }


def write_private_json(path: Path, payload: Any) -> None:
    """Atomically create a bounded owner-readable JSON transfer file.

    Args:
        path: New file beneath the owner's private temporary directory.
        payload: Finite JSON data, never an operator environment snapshot.

    Raises:
        ValueError: The serialized transfer exceeds the private byte bound.
        OSError: The new file cannot be created or durably written.

    The file is exclusive, mode 0600 and fsynced; its directory must be mode 0700.
    """
    encoded = json.dumps(payload, allow_nan=False, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_PRIVATE_BYTES:
        raise ValueError("Evaluation transfer exceeds its private byte bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _stop_worker(process: subprocess.Popen) -> str:
    """Terminate/reap the owned group, including children after leader exit.

    Returns:
        A content-free cleanup category. ``kill_sent`` is conservative: orphaned
        zombies can keep a process group visible temporarily. Trusted scorer code
        that deliberately detaches from this group is not sandboxed by the owner.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=2)
        return "not_present"
    grace = time.monotonic() + 2
    while time.monotonic() < grace:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            process.wait(timeout=2)
            return "terminated"
        except PermissionError:
            # macOS may reject signal-zero on a group consisting only of
            # terminated/zombie members. Verify process state rather than
            # interpreting denied probing as either liveness or successful kill.
            if not _has_running_group_member(process.pid):
                process.wait(timeout=2)
                return "terminated"
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if _has_running_group_member(process.pid):
            raise
    process.wait(timeout=2)
    return "kill_sent"


def _has_running_group_member(group_id: int) -> bool:
    """Inspect only PID/group/state when an owned group's signal probe is denied.

    Args:
        group_id: The worker's private process group, not a user-selected target.

    Returns:
        Whether any non-zombie member still belongs to this group.

    Raises:
        RuntimeError: A bounded process-state inventory could not be obtained.

    No command lines, environments, usernames or process content are requested,
    retained or printed. Failure is conservative: the owner cannot claim cleanup.
    This fallback uses the standard POSIX process-state utility, not extra packages.
    """
    probe = subprocess.run(
        ["ps", "-A", "-o", "pid=,pgid=,stat="],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=2,
        check=False,
    )
    if probe.returncode != 0 or len(probe.stdout) > 1024 * 1024:
        raise RuntimeError("Owned process-group state could not be verified")
    for line in probe.stdout.decode("ascii", errors="replace").splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == str(group_id) and not fields[2].startswith("Z"):
            return True
    return False


def evaluate_in_process(
    rows: list[dict[str, Any]],
    plan: Plan,
    traces: dict[str, Any],
    *,
    fail_fast: bool,
    phase: str,
    cancellation: Any = None,
) -> dict[str, Any]:
    """Execute native scoring with process-owned settings, credentials and cleanup.

    Args:
        rows: At most 10,000 captured attempts, containing only finite JSON data.
        plan: Frozen policy, never mutated or redirected by this owner.
        traces: Actual native Trace objects; public JSON serialization preserves them.
        fail_fast: Stop criteria after the first execution/persistence failure.
        phase: Internal readiness/quality tag, not a provider instruction.
        cancellation: Optional event with ``is_set`` checked every 100 milliseconds.

    Returns:
        The bounded native outcome, or a fixed safe process failure envelope.

    Environment credentials transfer only through OS process startup, never files.
    Temporary captured content is mode 0600 in a 0700 directory and removed after
    child reaping. The default deadline includes each frozen catalog attempt,
    startup/persistence grace and registered-scorer grace, capped at one day. An
    explicit operator ``BENCHMARK_EVALUATION_TIMEOUT_SECONDS`` may shorten it.
    Termination cannot revoke calls already committed to an external provider.
    """
    if len(rows) > MAX_CAPTURE_ROWS or len(traces) > MAX_CAPTURE_ROWS:
        return _phase_failure("evaluation_worker_failed")
    if cancellation is not None and cancellation.is_set():
        return _phase_failure("evaluation_worker_cancelled")
    values = dict(environment())
    values.update(NATIVE_ENVIRONMENT)
    values["BENCHMARK_EVALUATION_INTERNAL_PHASE"] = phase
    # The child must resolve the same installed module in notebooks/installed SDKs.
    module_root = str(Path(__file__).resolve().parent.parent)
    values["PYTHONPATH"] = os.pathsep.join(
        filter(None, [module_root, values.get("PYTHONPATH", "")])
    )
    catalog_count = sum(
        item.status == "ready" and not item.scorer.startswith("registered:")
        for item in plan.recommendations
    )
    budget = max(1, min(len(rows), plan.max_scored_requests))
    default_deadline = min(
        86_400,
        60
        + budget * catalog_count * (plan.judge_timeout_seconds * (plan.judge_max_retries + 1) + 10)
        + 1_800 * len(plan.registered_scorers),
    )
    outcome: dict[str, Any] | None = None
    try:
        deadline_seconds = float(
            values.get("BENCHMARK_EVALUATION_TIMEOUT_SECONDS", str(default_deadline))
        )
        if not 0 < deadline_seconds <= 86_400:
            raise ValueError("Invalid operator evaluation deadline")
        payload = {
            "rows": rows,
            "plan": plan.model_dump(mode="json"),
            "traces": {request: trace.to_json() for request, trace in traces.items()},
            "fail_fast": fail_fast,
            "phase": phase,
        }
        with tempfile.TemporaryDirectory(prefix="evalsurge-evaluation-") as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            source, destination = root / "input.json", root / "result.json"
            write_private_json(source, payload)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "benchmark_agents.evaluation_worker",
                    str(source),
                    str(destination),
                ],
                env=values,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + deadline_seconds
            worker_receipt: dict[str, Any] = {}
            outcome = _phase_failure("evaluation_worker_failed")
            try:
                while process.poll() is None:
                    if cancellation is not None and cancellation.is_set():
                        outcome = _phase_failure("evaluation_worker_cancelled")
                        break
                    if time.monotonic() >= deadline:
                        outcome = _phase_failure("evaluation_worker_timeout")
                        break
                    time.sleep(0.1)
                if (
                    process.returncode == 0
                    and destination.exists()
                    and destination.stat().st_size <= MAX_PRIVATE_BYTES
                ):
                    result = json.loads(destination.read_text())
                    worker_receipt = result.pop("worker", {}) if isinstance(result, dict) else {}
                    if isinstance(result, dict) and isinstance(result.get("status"), str):
                        outcome = result
            finally:
                cleanup_error = None
                try:
                    cleanup = _stop_worker(process)
                except Exception:  # noqa: BLE001
                    cleanup = "unverified"
                    cleanup_error = "worker_cleanup_failed"
                    if outcome["status"] != "failed":
                        outcome["status"] = "failed"
                        outcome["error"] = _phase_failure("evaluation_worker_failed")["error"]
                receipt_path = values.get(
                    "BENCHMARK_EVALUATION_WORKER_RECEIPT_JOURNAL"
                ) or values.get("BENCHMARK_EVALUATION_JUDGE_ATTEMPT_JOURNAL")
                if receipt_path:
                    from .evaluation_attempts import record_private_event

                    try:
                        record_private_event(
                            Path(receipt_path),
                            {
                                "kind": "worker_receipt",
                                "phase": phase,
                                "pid": process.pid,
                                "exit_code": process.returncode,
                                "reaped": process.poll() is not None,
                                "process_group_cleanup": cleanup,
                                "cleanup_error": cleanup_error,
                                "status": outcome["status"],
                                "phase_error_code": (outcome.get("error") or {}).get("code"),
                                **worker_receipt,
                            },
                        )
                    except Exception:  # noqa: BLE001
                        if outcome["status"] != "failed":
                            outcome["status"] = "failed"
                            outcome["error"] = _phase_failure("evaluation_worker_failed")["error"]
            return outcome
    except Exception:  # noqa: BLE001
        return (
            outcome
            if outcome and outcome["status"] == "failed"
            else _phase_failure("evaluation_worker_failed")
        )


def verify_durable_assessments(
    frame: Any,
    selected: list[dict[str, Any]],
    metric_name: str,
    run_id: str,
    client: Any,
) -> Any:
    """Filter native results to exact durable request/name/source-run evidence.

    Args:
        frame: Native result DataFrame, including serialized evaluation traces.
        selected: Frozen selected request IDs; never joined by prompt or row order.
        metric_name: Exact frozen assessment name.
        run_id: Evaluation run owning the new feedback metadata.
        client: Native client for the same frozen store.

    Returns:
        A frame containing only unique durably verified trace/assessment records.
        Missing, duplicate, foreign-run or inconsistent evidence cannot count as a
        completed score. Provider errors retain their native safe classification.

    Native ``Assessment.run_id`` is not authoritative here; source-run metadata is.
    These reads occur after synchronous persistence and outside measured load.
    """
    import pandas as pd
    from mlflow.entities import Feedback, Trace

    from .evaluation_details import REQUEST_TAG

    if frame is None:
        return None
    wanted = {row["request_id"] for row in selected}
    candidates: dict[str, list[dict[str, Any]]] = {}
    for record in frame.to_dict("records"):
        tags = record.get("tags")
        request_id = tags.get(REQUEST_TAG) if isinstance(tags, dict) else None
        if request_id in wanted:
            candidates.setdefault(request_id, []).append(record)
    verified = []
    for request_id, records in candidates.items():
        if len(records) != 1:
            # Retain duplicates so the public extractor reports ambiguity, not
            # an accidentally successful aggregate or an invented rationale.
            verified.extend(records)
            continue
        record = records[0]
        try:
            raw_trace = record.get("trace")
            trace = Trace.from_json(raw_trace) if isinstance(raw_trace, str) else raw_trace
            if not isinstance(trace, Trace):
                continue
            durable = client.get_trace(trace.info.trace_id)
            if (
                durable.info.trace_id != trace.info.trace_id
                or durable.info.tags.get(REQUEST_TAG) != request_id
            ):
                continue
            feedback = [
                item
                for item in durable.info.assessments
                if isinstance(item, Feedback)
                and item.valid is not False
                and item.trace_id == durable.info.trace_id
                and item.name == metric_name
                and (item.metadata or {}).get("mlflow.assessment.sourceRunId") == run_id
            ]
            if len(feedback) != 1:
                continue
            item = feedback[0]
            # Do not trust a transient result value or rationale over the store.
            record[f"{metric_name}/value"] = item.value
            record[f"{metric_name}/rationale"] = item.rationale
            record[f"{metric_name}/error_message"] = item.error_message
            record["assessments"] = [item.to_dictionary()]
            verified.append(record)
        except Exception:  # noqa: BLE001
            continue
    return pd.DataFrame(verified)
