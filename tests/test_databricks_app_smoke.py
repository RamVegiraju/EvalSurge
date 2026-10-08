"""Consent/budget checks and real Locust validation without paid App traffic."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from benchmark_agents import target_resolver
from benchmark_agents.connections import Connection
from benchmark_agents.models import Target
from scripts.validation import databricks_app_smoke as smoke
from tests.test_agent_runtime_protocol import runtime_endpoint  # noqa: F401


def arguments(*extra: str) -> list[str]:
    return [
        "--profile",
        "chosen-private-profile",
        "--app-name",
        "sample-agent",
        "--prompt",
        "Hello",
        *extra,
    ]


def test_default_is_content_free_dry_run_without_discovery(monkeypatch, capsys) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Dry-run must not perform discovery, auth, storage or traffic")

    monkeypatch.setattr(smoke, "execute", forbidden)
    monkeypatch.setattr(target_resolver, "resolve_registered_target", forbidden)
    assert smoke.main(arguments()) == 0
    output = capsys.readouterr().out
    assert "chosen-private-profile" not in output and "Hello" not in output
    record = json.loads(output)
    assert record["live"] is False
    assert record["max_measured_invocations"] == 2
    assert record["max_total_invocations"] == 3
    assert record["evaluation_mode"] == "off"


@pytest.mark.parametrize(
    "extra",
    [
        ["--live"],
        ["--live", "--accept-paid-traffic"],
        ["--max-requests", "501"],
        ["--max-requests", "0"],
        ["--concurrency", "6"],
        ["--concurrency", "0"],
        ["--duration", "181"],
        ["--duration", "nan"],
        ["--timeout", "inf"],
        ["--timeout", "61"],
    ],
)
def test_consent_and_small_finite_budgets_are_required(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        smoke.parse_options(arguments(*extra))


def test_five_users_and_three_minute_budget_are_explicit_and_bounded() -> None:
    options = smoke.parse_options(
        arguments("--concurrency", "5", "--duration", "180", "--max-requests", "500")
    )
    record = smoke.budget_record(options)
    assert record["concurrency"] == 5
    assert record["dispatch_seconds"] == 180
    assert record["max_measured_invocations"] == 500
    assert record["max_total_invocations"] == 501
    assert not record["live"]


def test_direct_execution_cannot_bypass_live_consent() -> None:
    options = smoke.parse_options(arguments())
    with pytest.raises(ValueError, match="explicit consent"):
        smoke.execute(options)


def test_existing_records_are_not_overwritten_or_reinvoked(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "validation.json").write_text("existing protected evidence")
    options = smoke.parse_options(
        arguments(
            "--live",
            "--accept-paid-traffic",
            "--concurrency",
            "5",
            "--max-requests",
            "10",
            "--artifact-dir",
            str(tmp_path),
        )
    )

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Existing store must be rejected before App discovery")

    monkeypatch.setattr(target_resolver, "resolve_registered_target", forbidden)
    with pytest.raises(ValueError, match="dedicated artifact directory"):
        smoke.execute(options)
    assert (tmp_path / "validation.json").read_text() == "existing protected evidence"


async def test_live_harness_uses_one_probe_and_bounded_real_locust(
    runtime_endpoint: Any,  # noqa: F811 - shared native HTTP fixture, resolved by pytest
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control discovery only; native HTTP, adapter, coordinator and Locust remain real."""
    url, received = runtime_endpoint
    selections = []

    def resolve(alias, presets):
        selection = presets[alias]
        selections.append((selection.profile, selection.app_name, selection.protocols))
        return Target(
            url=url, adapter="databricks-agent-runtime", session_per_request=True
        ), Connection(url=url)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Performance-only validation must not construct planner/judge clients")

    monkeypatch.setattr(target_resolver, "resolve_registered_target", resolve)
    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)
    options = smoke.parse_options(
        arguments(
            "--live",
            "--accept-paid-traffic",
            "--concurrency",
            "5",
            "--max-requests",
            "10",
            "--artifact-dir",
            str(tmp_path),
        )
    )
    code, record = await asyncio.to_thread(smoke.execute, options)
    assert code == 0 and record["passed"]
    assert len(received) == 11
    assert record["concurrency"] == record["metrics"]["configured_concurrency"] == 5
    assert record["metrics"]["requests"] == 10
    assert record["observed_probe_attempts"] == 1
    assert record["observed_measured_attempts"] == 10
    assert record["observed_total_attempts"] == 11
    assert record["inference_preflight"] == "passed"
    assert selections == [("chosen-private-profile", "sample-agent", ("databricks-agent-runtime",))]
    assert json.loads((tmp_path / "validation.json").read_text()) == record
    assert "chosen-private-profile" not in json.dumps(record)
    assert record["sustainable_capacity_established"] is False


async def test_failed_probe_is_recorded_without_measured_or_repeat_calls(
    endpoint: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A controlled malformed native response preserves failure and prevents load."""
    base, server = endpoint

    def resolve(alias, presets):
        url = base + "/json-malformed"
        return Target(url=url, adapter="databricks-agent-runtime"), Connection(url=url)

    monkeypatch.setattr(target_resolver, "resolve_registered_target", resolve)
    options = smoke.parse_options(
        arguments(
            "--live",
            "--accept-paid-traffic",
            "--concurrency",
            "5",
            "--max-requests",
            "10",
            "--artifact-dir",
            str(tmp_path),
        )
    )
    code, record = await asyncio.to_thread(smoke.execute, options)
    assert code == 1 and record["passed"] is False
    assert record["inference_preflight"] == "failed"
    assert record["load_status"] == "skipped"
    assert server["received"] == 1
    assert record["metrics"]["requests"] == record["observed_measured_attempts"] == 0
    assert record["observed_probe_attempts"] == record["observed_total_attempts"] == 1
    assert record["fail_fast_confirmed"] is True
    assert record["preflight_error"]["code"] == "invalid_response"
    assert "Load test did not start" in record["preflight_error"]["message"]
    assert "private" not in json.dumps(record)
    assert json.loads((tmp_path / "validation.json").read_text()) == record
