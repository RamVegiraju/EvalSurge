"""Small remote CLI; credentials come from environment, never command arguments.

Config files are local operator data and parsed without execution. Console output
contains only validated lifecycle identifiers/status and fixed diagnostics. It
never dumps report/configuration bodies or automatically retries submissions.
"""

import argparse
import importlib
import json
import math
import os
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from benchmark_agents.v2_models import RunCreate

from .remote import MAX_REQUEST_BYTES, RemoteClient, RemoteError


class _ConfigurationError(ValueError):
    """Safe user-input diagnostic, excluding private argument/configuration text."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ConfigurationError("Invalid command arguments; use evalsurge --help for usage.")


def _parser() -> argparse.ArgumentParser:
    """Allow service options before or after the command without echoing errors."""
    parser = _Parser(description="Run benchmarks through an EvalSurge v2 API.")

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

    service_options(parser)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    run = commands.add_parser("run", help="Submit one JSON or optional YAML configuration")
    service_options(run)
    run.add_argument("config", type=Path)
    run.add_argument("--wait", action="store_true", help="Wait for report readiness")
    run.add_argument("--timeout", type=float, default=3600, help="Total wait budget in seconds")
    run.add_argument(
        "--open-report", action="store_true", help="Open a credential-free report shell"
    )
    run.add_argument("--idempotency-key", help="Explicit submission recovery key")
    doctor = commands.add_parser("doctor", help="Check service capabilities without target calls")
    service_options(doctor)
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
        RunCreate.model_validate(body)
        encoded = json.dumps(body, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise _ConfigurationError(
            "Configuration must contain finite JSON-compatible values."
        ) from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise _ConfigurationError("Configuration exceeds the eight-million-byte limit.")
    return body


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[..., RemoteClient] = RemoteClient,
    opener: Callable[[str], bool] = webbrowser.open,
) -> int:
    """Execute a bounded remote command, returning 0/1/2/130 exit codes.

    Args:
        argv: Argument sequence; omission reads sys.argv.
        client_factory: Transport factory for controlled offline integration tests.
        opener: Browser launcher; receives only a locally constructed report URL.

    Returns:
        Zero for successful execution, one for service/run failure, two for invalid
        local input, or 130 for interruption. Interrupted/timed-out runs continue.

    No report or capability body is printed: these may contain protected content.
    """
    try:
        args = _parser().parse_args(argv)
        config = _configuration(args.config) if args.command == "run" else None
        if (
            args.command == "run"
            and args.wait
            and (not math.isfinite(args.timeout) or args.timeout <= 0)
        ):
            raise _ConfigurationError("Wait timeout must be a positive finite number of seconds.")
        url = getattr(args, "url", os.getenv("EVALSURGE_URL", "http://127.0.0.1:8000"))
        with client_factory(
            url,
            api_key=os.getenv("EVALSURGE_API_KEY"),
            request_timeout=getattr(args, "request_timeout", 30),
        ) as client:
            if args.command == "doctor":
                capabilities = client.capabilities()
                if capabilities.get("api_version") != "v2":
                    print("Service responded with unsupported capabilities.", file=sys.stderr)
                    return 1
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
            run = client.start(config, idempotency_key=args.idempotency_key)
            print(f"Run {run.id} accepted.")
            if args.wait:
                report = run.wait(timeout=args.timeout)
                print(f"Run {run.id} {report['run']['status']}.")
            if args.open_report:
                try:
                    opened = opener(run.report_url)
                except (OSError, webbrowser.Error):
                    opened = False
                if not opened:
                    print("Report browser could not be opened.", file=sys.stderr)
                    return 1
            print(f"Report: {run.report_url}")
            return 0
    except RemoteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except _ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (ValueError, TypeError):
        # All validation messages are fixed; never expose unexpected caller data.
        print(
            "Invalid configuration or service settings; check JSON/YAML, URL, and timing limits.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("Interrupted; server-side work was not cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
