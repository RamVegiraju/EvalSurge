"""Fixed message protocols reject input loss before admission or target traffic."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from benchmark_agents import coordinator
from benchmark_agents.api import create_app
from benchmark_agents.coordinator import CoordinatorError
from benchmark_agents.models import Load, Sample
from benchmark_agents.runner import payload
from evalsurge import Agent, EvalSurge
from tests.test_template import configuration
from tests.test_v2 import request_body

PROTOCOLS = ["openai-chat", "mlflow-agent-server", "databricks-agent-runtime"]


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize(
    "field", ["custom_inputs", "actor", "model", "resume", "background", "private-field-name"]
)
def test_fixed_message_inputs_do_not_silently_discard_fields(protocol: str, field: str) -> None:
    """Unsupported top-level inference values cannot become an altered benchmark."""
    request = configuration()
    request.target.adapter = protocol
    sample = Sample(inputs={"query": "Hello", field: "synthetic-private-input-value"})
    with pytest.raises(ValueError, match="Unsupported inference fields") as failure:
        payload(request, sample)
    assert "synthetic-private-input-value" not in str(failure.value)
    assert "private-field-name" not in str(failure.value)


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_query_and_messages_are_not_ambiguous_alternatives(protocol: str) -> None:
    request = configuration()
    request.target.adapter = protocol
    with pytest.raises(ValueError, match="exactly one"):
        payload(request, Sample(inputs={"query": "ignored", "messages": [{"role": "user"}]}))


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_nested_message_content_is_transmitted_without_stripping(protocol: str) -> None:
    request = configuration()
    request.target.adapter = protocol
    message = {
        "role": "user",
        "content": [{"type": "input_text", "text": "Hello"}],
        "name": "operator-reviewed-caller",
    }
    sample = Sample(inputs={"messages": [message]})
    encoded = payload(request, sample)
    assert encoded["messages" if protocol == "openai-chat" else "input"] == [message]
    assert sample.inputs == {"messages": [message]}


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_rest_rejects_unsupported_inputs_before_planning_and_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    """Actual API envelopes give safe corrective guidance without accepting a run."""
    monkeypatch.setenv(
        "BENCHMARK_CONNECTIONS",
        json.dumps({"support": {"url": "http://127.0.0.1:9001/chat"}}),
    )

    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Invalid inputs must not start planning or inference")

    monkeypatch.setattr(coordinator, "create_plan", forbidden)
    monkeypatch.setattr(coordinator, "run_preflight", forbidden)
    body = configuration().model_dump(mode="json") if version == "v1" else request_body()
    inputs = (
        body["evaluation"]["samples"][0]["inputs"] if version == "v1" else body["cases"][0]["input"]
    )
    inputs["custom_inputs"] = {"secret": "synthetic-private-input-value"}
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        rejected = client.post(f"/{version}/runs", json=body)
        assert rejected.status_code == 422
        assert "Unsupported inference fields" in rejected.text
        assert "custom_inputs" in rejected.text
        assert "synthetic-private-input-value" not in rejected.text
        assert not client.app.state.coordinator.index
    assert not (tmp_path / "plans").exists()


async def test_local_rejects_unsupported_inputs_before_admission(tmp_path: Path) -> None:
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        with pytest.raises(CoordinatorError, match="Unsupported inference fields"):
            await client.start(
                agent=Agent.http("http://127.0.0.1:9001/chat"),
                cases=[Sample(inputs={"query": "Hello", "actor": "private-value"})],
                load=Load(max_requests=1),
            )
    assert not (tmp_path / "plans").exists()
