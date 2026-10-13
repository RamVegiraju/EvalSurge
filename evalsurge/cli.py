"""Direct or optional-server CLI; credentials never enter benchmark requests.

Config files are local operator data and parsed without execution. Console output
contains validated lifecycle/metric summaries and fixed diagnostics. Protected
report bodies require explicit --json output. Submissions are never retried.
"""

import argparse
import importlib
import json
import math
import os
import re
import sys
import time
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel

from benchmark_agents.v2_models import LifecycleStatus, PhaseStates
from benchmark_agents.validation import RequestValidationError, validate_request

from .remote import MAX_REQUEST_BYTES, RemoteClient, RemoteError
from .summary import format_summary


class _ConfigurationError(ValueError):
    """Safe user-input diagnostic, excluding private argument/configuration text."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ConfigurationError("Invalid command arguments; use evalsurge --help for usage.")


def _parser() -> argparse.ArgumentParser:
    """Allow service options before or after the command without echoing errors."""
    parser = _Parser(description="Run benchmarks directly or through an optional v2 API.")

    def service_options(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--url", default=argparse.SUPPRESS, help="HTTPS or loopback service URL"
        )
        target.add_argument(
            "--request-timeout",
            type=float,
            default=argparse.SUPPRESS,
            help="Per-I/O HTTP timeout in seconds (default: 30)",
        )
        target.add_argument(
            "--local",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Execute on this machine; no API server required",
        )
        target.add_argument(
            "--settings",
            type=Path,
            default=argparse.SUPPRESS,
            help="Local operator TOML/YAML settings, outside the run request",
        )
        target.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Print structured output; run reports contain protected evidence",
        )

    service_options(parser)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    run = commands.add_parser("run", help="Submit one JSON or optional YAML configuration")
    service_options(run)
    run.add_argument("config", type=Path)
    run.add_argument("--wait", action="store_true", help="Wait for report readiness")
    run.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show content-free live phase updates on stderr (automatic for interactive waits)",
    )
    run.add_argument("--timeout", type=float, default=3600, help="Total wait budget in seconds")
    run.add_argument(
        "--open-report", action="store_true", help="Open a credential-free report shell"
    )
    run.add_argument("--idempotency-key", help="Explicit submission recovery key")
    run.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Override operator artifact storage (unconfigured default: artifacts)",
    )
    doctor = commands.add_parser("doctor", help="Check service capabilities without target calls")
    service_options(doctor)
    targets = commands.add_parser(
        "targets", help="List configured public aliases, without target calls"
    )
    service_options(targets)
    return parser


def _configuration(path: Path) -> dict[str, Any]:
    """Parse an eight-million-byte local JSON/YAML document without executing it.

    Args:
        path: Operator-selected local file, read-only; optional YAML uses safe_load.

    Returns:
        JSON-compatible v2 configuration after schema and encoded-size checks.

    Raises:
        _ConfigurationError: Unreadable, oversized, unsupported, or invalid input.
            Messages never contain filenames, source text, or parser diagnostics.
    """
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_REQUEST_BYTES + 1)
    except OSError:
        raise _ConfigurationError("Configuration file could not be read.") from None
    if len(raw) > MAX_REQUEST_BYTES:
        raise _ConfigurationError("Configuration exceeds the eight-million-byte limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _ConfigurationError("Configuration must be UTF-8 JSON or YAML.") from None
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            yaml = importlib.import_module("yaml")
        except ModuleNotFoundError:
            raise _ConfigurationError(
                "YAML configuration requires optional PyYAML; JSON is supported without it."
            ) from None
        try:
            if any(isinstance(token, yaml.tokens.AliasToken) for token in yaml.scan(text)):
                raise _ConfigurationError(
                    "YAML aliases are unsupported; use independent case values."
                )
            body = yaml.safe_load(text)
        except _ConfigurationError:
            raise
        except (yaml.YAMLError, ValueError, TypeError, RecursionError):
            raise _ConfigurationError("Configuration is not valid safe YAML.") from None
    else:
        try:
            body = json.loads(text)
        except (ValueError, RecursionError):
            raise _ConfigurationError("Configuration is not valid JSON.") from None
    if not isinstance(body, dict) or not body:
        raise _ConfigurationError("Configuration must be a nonempty JSON object.")
    try:
        validate_request(body)
    except RequestValidationError as error:
        raise _ConfigurationError(str(error)) from None
    try:
        encoded = json.dumps(body, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise _ConfigurationError(
            "Configuration must contain finite JSON-compatible values."
        ) from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise _ConfigurationError("Configuration exceeds the eight-million-byte limit.")
    return body


def _document(value: Any) -> dict[str, Any]:
    """Detach a typed or legacy response for presentation without invoking a target."""
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def _summary(report: dict[str, Any]) -> None:
    """Print the shared public summary, never prompts/rationales or raw errors.

    Args:
        report: Validated typed report or the legacy remote report document.

    Side effects:
        Writes to stdout. Missing historical fields remain unavailable. A low
        quality pass rate does not change the exit code; threshold gates remain
        a later milestone. Explicit --json output bypasses this renderer.
    """
    print(format_summary(report))


def _public_targets(capabilities: dict[str, Any]) -> list[dict[str, Any]]:
    """Project only bounded public alias/protocol fields from capability documents."""
    allowed = {"openai-chat", "mlflow-agent-server", "http-json", "databricks-agent-runtime"}
    targets = capabilities.get("targets", [])
    public = []
    for target in targets if isinstance(targets, (list, tuple)) else []:
        if not isinstance(target, dict):
            continue
        name = target.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
            continue
        declared = target.get("protocols", [])
        protocols = (
            [p for p in declared if isinstance(p, str) and p in allowed]
            if isinstance(declared, (list, tuple))
            else []
        )
        public.append({"name": name, "protocols": protocols})
    return public


def _public_capabilities(capabilities: dict[str, Any]) -> dict[str, Any]:
    """Project dependency-light safe discovery/readiness JSON, not raw server data."""
    readiness = {"configured", "needs_configuration", "disabled"}
    evaluation = capabilities.get("evaluation", {})
    tracing = capabilities.get("tracing", {})
    return {
        "api_version": "v2",
        "targets": _public_targets(capabilities),
        "evaluation": {
            key: evaluation[key]
            for key in ("planner", "catalog_judges", "default_mode")
            if isinstance(evaluation, dict)
            and isinstance(evaluation.get(key), str)
            and evaluation.get(key) in (readiness if key != "default_mode" else {"off"})
        },
        "tracing": {"readiness": tracing["readiness"]}
        if isinstance(tracing, dict)
        and isinstance(tracing.get("readiness"), str)
        and tracing["readiness"] in readiness
        else {},
        "runtime_verified": False,
    }


def _targets(capabilities: dict[str, Any]) -> None:
    """Print only reviewed public aliases/protocol names, never connection settings."""
    targets = _public_targets(capabilities)
    for target in targets:
        print(f"{target['name']}: {', '.join(target['protocols']) or 'protocol unconfigured'}")
    if not targets:
        print(
            "No configured targets. Register an alias in operator settings before submitting a run."
        )
    print("Static configuration only; authentication and target health are unverified.")


class _LiveProgress:
    """Bounded lifecycle presentation, never a live metric or request-content logger."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._last_update = float("-inf")
        self._last_state: tuple[str, tuple[str, ...]] | None = None

    def __call__(self, status: BaseModel | dict[str, Any]) -> None:
        """Print allowlisted phases on changes or a ten-second heartbeat.

        Args:
            status: Existing waiter observation, not protected result/report data.

        Side Effects:
            Writes a bounded line to stderr. Names, URLs, inputs, provider errors
            and unrecognized values are omitted; JSON stdout remains untouched.
            Rendering occurs in the caller, never the Locust request hot path.
        """
        body = _document(status)
        value = body.get("status")
        lifecycle = (
            value if isinstance(value, str) and value in get_args(LifecycleStatus) else "unknown"
        )
        phases = body.get("phases")
        parts = []
        if isinstance(phases, dict):
            for name, field in PhaseStates.model_fields.items():
                phase = phases.get(name)
                if isinstance(phase, str) and phase in get_args(field.annotation):
                    parts.append(f"{name}={phase}")
        state = (lifecycle, tuple(parts))
        now = self._clock()
        if state == self._last_state and now - self._last_update < 10:
            return
        elapsed = max(0, now - self._started)
        detail = f" | {', '.join(parts)}" if parts else ""
        print(f"[{elapsed:.0f}s] {lifecycle}{detail}", file=sys.stderr)
        self._last_update = now
        self._last_state = state


def _run(
    client: Any,
    args: argparse.Namespace,
    config: dict[str, Any],
    *,
    local: bool,
    opener: Callable[[str], bool],
) -> int:
    """Submit once, optionally wait and present a protected report by explicit choice.

    Args:
        client: Open unified direct context or compatible remote HTTP client.
        args: Parsed bounded options; local execution always waits before cleanup.
        config: Validated v2 request, detached from operator settings.
        local: Whether this process owns the runner; no browser shell is implied.
        opener: Credential-free remote report browser launcher.

    Returns:
        Zero on lifecycle success or one if a requested browser could not open.
        Low/false quality verdicts are not execution failures or threshold gates.
    """
    structured = getattr(args, "json", False)
    run = client.start(config, idempotency_key=args.idempotency_key)
    if not structured:
        print(f"Run {run.id} accepted.")
    report = None
    if args.wait or local:
        progress = args.progress
        if progress is None:
            progress = not structured and sys.stderr.isatty()
        report = _document(
            run.wait(timeout=args.timeout, on_status=_LiveProgress())
            if progress
            else run.wait(timeout=args.timeout)
        )
        if not structured:
            _summary(report)
    if args.open_report:
        try:
            opened = opener(run.report_url)
        except (OSError, webbrowser.Error):
            opened = False
        if not opened:
            print("Report browser could not be opened.", file=sys.stderr)
            return 1
    if structured:
        print(
            json.dumps(
                report
                if report is not None
                else {
                    "id": str(run.id),
                    "status": "accepted",
                    "report_url": run.report_url,
                },
                allow_nan=False,
                ensure_ascii=False,
            )
        )
    elif local:
        print("Report: saved in local artifacts; use run.report() for typed retrieval.")
    else:
        print(f"Report: {run.report_url}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[..., RemoteClient] = RemoteClient,
    opener: Callable[[str], bool] = webbrowser.open,
) -> int:
    """Execute a bounded direct or remote command, returning 0/1/2/130 exit codes.

    Args:
        argv: Argument sequence; omission reads sys.argv.
        client_factory: Transport factory for controlled offline integration tests.
        opener: Browser launcher; receives only a locally constructed report URL.

    Returns:
        Zero for successful execution, one for service/run failure, two for invalid
        local input, or 130 for interruption. Remote waiter interruption/timeout
        leaves service work active. Local execution exits its context, stopping
        new dispatch, draining owned work and releasing its artifact lock.

    --json explicitly permits protected structured report output. Ordinary
    summaries never print prompts, references, rationales or raw error payloads.
    """
    local = False
    try:
        args = _parser().parse_args(argv)
        local = getattr(args, "local", False)
        if local and hasattr(args, "url"):
            raise _ConfigurationError("--local cannot be combined with a service --url.")
        if not local and hasattr(args, "settings"):
            raise _ConfigurationError(
                "--settings requires --local; remote targets are server-owned."
            )
        if local and args.command == "run" and args.open_report:
            raise _ConfigurationError(
                "--open-report needs an API report server; local runs return typed report data."
            )
        if args.command == "run" and args.progress is True and not (args.wait or local):
            raise _ConfigurationError("--progress requires --wait or --local.")
        config = _configuration(args.config) if args.command == "run" else None
        if (
            args.command == "run"
            and (args.wait or local)
            and (not math.isfinite(args.timeout) or args.timeout <= 0)
        ):
            raise _ConfigurationError("Wait timeout must be a positive finite number of seconds.")
        if local:
            from benchmark_agents.diagnostics import doctor
            from benchmark_agents.settings import load_settings

            if args.command in {"doctor", "targets"}:
                findings = doctor(getattr(args, "settings", None))
                if args.command == "targets":
                    capabilities = _document(findings.capabilities) if findings.capabilities else {}
                    if getattr(args, "json", False):
                        print(
                            json.dumps(
                                {
                                    "targets": _public_targets(capabilities),
                                    "runtime_verified": False,
                                }
                            )
                        )
                    else:
                        _targets(capabilities)
                elif getattr(args, "json", False):
                    print(findings.model_dump_json())
                else:
                    for check in findings.checks:
                        print(f"{check.status}: {check.message}")
                return 0 if findings.ok else 1
            from benchmark_agents.coordinator import CoordinatorError

            from .client import RunFailed
            from .facade import EvalSurge

            assert config is not None
            try:
                with EvalSurge(
                    artifact_dir=args.artifact_dir,
                    settings=load_settings(getattr(args, "settings", None)),
                ) as client:
                    return _run(client, args, config, local=True, opener=opener)
            except RunFailed as error:
                if getattr(args, "json", False):
                    print(json.dumps(_document(error.report), allow_nan=False, ensure_ascii=False))
                print(
                    "Benchmark execution failed; inspect retained local report and phase outcomes.",
                    file=sys.stderr,
                )
                return 1
            except CoordinatorError:
                print(
                    "Benchmark execution failed; inspect retained local report and phase outcomes.",
                    file=sys.stderr,
                )
                return 1
            except TimeoutError:
                print(
                    "Wait timed out; local context stopped new dispatch and drained owned work.",
                    file=sys.stderr,
                )
                return 1
        url = getattr(args, "url", os.getenv("EVALSURGE_URL", "http://127.0.0.1:8000"))
        with client_factory(
            url,
            api_key=os.getenv("EVALSURGE_API_KEY"),
            request_timeout=getattr(args, "request_timeout", 30),
        ) as client:
            if args.command == "targets":
                capabilities = client.capabilities()
                if getattr(args, "json", False):
                    print(
                        json.dumps(
                            {"targets": _public_targets(capabilities), "runtime_verified": False}
                        )
                    )
                else:
                    _targets(capabilities)
                return 0
            if args.command == "doctor":
                capabilities = client.capabilities()
                if capabilities.get("api_version") != "v2":
                    print("Service responded with unsupported capabilities.", file=sys.stderr)
                    return 1
                if getattr(args, "json", False):
                    print(json.dumps(_public_capabilities(capabilities)))
                    return 0
                print("EvalSurge v2 service is reachable.")
                targets = capabilities.get("targets")
                if isinstance(targets, (list, tuple)):
                    print(f"Registered targets: {len(targets)}.")
                evaluation = capabilities.get("evaluation")
                tracing = capabilities.get("tracing")
                readiness = {
                    "configured": "configured",
                    "needs_configuration": "needs configuration",
                    "disabled": "disabled",
                }
                if isinstance(evaluation, dict):
                    for key, label in (
                        ("planner", "Planner"),
                        ("catalog_judges", "Catalog judges"),
                    ):
                        value = evaluation.get(key)
                        if isinstance(value, str) and value in readiness:
                            print(f"{label}: {readiness[value]}.")
                if isinstance(tracing, dict):
                    value = tracing.get("readiness")
                    if isinstance(value, str) and value in readiness:
                        print(f"Tracing: {readiness[value]}.")
                print("Runtime authentication and target health are unverified.")
                return 0
            assert config is not None
            return _run(client, args, config, local=False, opener=opener)
    except RemoteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except _ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RequestValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ImportError:
        print(
            "Direct CLI execution requires 'evalsurge[local]' "
            "(or the compatible 'evalsurge[server]' extra). Neither starts an API server.",
            file=sys.stderr,
        )
        return 2
    except (ValueError, TypeError):
        # All validation messages are fixed; never expose unexpected caller data.
        print(
            "Invalid configuration or service settings; check JSON/YAML, URL, and timing limits.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print(
            "Interrupted; local context requested cancellation and drained owned work."
            if local
            else "Interrupted; server-side work was not cancelled.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
