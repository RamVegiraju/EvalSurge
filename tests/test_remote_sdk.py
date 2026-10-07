"""Remote SDK regressions over real httpx requests and deterministic transports."""

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from uuid import UUID

import httpx
import pytest

from benchmark_agents.v2_models import RunCreate
from evalsurge.remote import (
    RemoteClient,
    RemoteConflictError,
    RemoteProtocolError,
    RemoteRateLimitError,
    RemoteRunFailed,
    RemoteTimeout,
    RemoteTransportError,
    RemoteUnauthorizedError,
)

RUN_ID = UUID("51d78660-11d8-486c-8399-fd9e74da19ce")
SECRET = "private-api-key"
CONFIG = {
    "target": {"connection_id": "support"},
    "cases": [{"input": {"prompt": "hello"}}],
    "load": {"max_requests": 1},
}


class Clock:
    """Monotonic fake clock; sleeps advance time without wall-clock delays."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_start_wait_report_cancel_and_auth_without_submission_retry() -> None:
    clock = Clock()
    requests: list[httpx.Request] = []
    statuses = iter(["running", "completed"])

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["X-API-Key"] == SECRET
        if request.method == "POST" and request.url.path == "/v2/runs":
            assert request.headers["Idempotency-Key"] == "once"
            assert json.loads(request.content) == CONFIG
            return httpx.Response(
                202, json={"id": str(RUN_ID), "status": "queued"}, headers={"Retry-After": "2"}
            )
        if request.url.path.endswith("/report"):
            assert request.url.params.get("limit") in {"25", "5"}
            return httpx.Response(200, json={"run": {"id": str(RUN_ID), "status": "completed"}})
        if request.url.path.endswith("/cancel"):
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "cancelled"})
        return httpx.Response(
            200, json={"id": str(RUN_ID), "status": next(statuses), "poll_after_seconds": 3}
        )

    with RemoteClient(
        "https://api.example",
        api_key=SECRET,
        transport=httpx.MockTransport(handle),
        sleep=clock.sleep,
        clock=clock.time,
    ) as client:
        run = client.start(CONFIG, idempotency_key="once")
        assert run.id == RUN_ID
        assert SECRET not in repr(client) + repr(run)
        assert run.wait(timeout=10)["run"]["status"] == "completed"
        assert run.report(offset=1, limit=5)["run"]["id"] == str(RUN_ID)
        assert run.cancel()["status"] == "cancelled"
        assert SECRET not in run.report_url
    assert clock.sleeps == [2, 3]
    assert (
        sum(request.method == "POST" and request.url.path == "/v2/runs" for request in requests)
        == 1
    )


def test_wait_honors_retry_after_http_date_and_both_poll_hints() -> None:
    clock = Clock()
    calls = 0
    date = format_datetime(datetime.fromtimestamp(1005, timezone.utc), usegmt=True)

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": "completed"}})
        return httpx.Response(
            200,
            json={
                "id": str(RUN_ID),
                "status": "running" if calls == 1 else "completed",
                "poll_after_seconds": 3,
            },
            headers={"Retry-After": date if calls == 1 else "0"},
        )

    with RemoteClient(
        "https://api.example",
        transport=httpx.MockTransport(handle),
        sleep=clock.sleep,
        clock=clock.time,
        wall_clock=lambda: 1000,
    ) as client:
        assert client.wait(RUN_ID, timeout=10)["run"]["status"] == "completed"
    assert clock.sleeps == [5]


@pytest.mark.parametrize("status", ["failed", "cancelled", "interrupted"])
def test_terminal_run_failures_preserve_report_without_echoing_details(status: str) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": status, "private": SECRET}})
        return httpx.Response(200, json={"id": str(RUN_ID), "status": status})

    with RemoteClient("https://api.example", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RemoteRunFailed) as failed:
            client.wait(RUN_ID)
        assert failed.value.report["run"]["private"] == SECRET
        assert SECRET not in str(failed.value) + repr(failed.value)
        assert client.report(RUN_ID)["run"]["status"] == status


@pytest.mark.parametrize(
    "status,exception",
    [(401, RemoteUnauthorizedError), (429, RemoteRateLimitError), (409, RemoteConflictError)],
)
def test_error_envelope_parsing_is_typed_and_never_echoes_server_secrets(
    status: int, exception: type[Exception]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json={"error": {"code": "safe_code", "message": SECRET, "request_id": "safe-request"}},
            headers={"Retry-After": "4"},
        )

    with RemoteClient(
        "https://api.example", api_key=SECRET, transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(exception) as failure:
            client.start(CONFIG)
        assert failure.value.status_code == status
        assert failure.value.code == "safe_code"
        assert failure.value.request_id == "safe-request"
        assert failure.value.retry_after_seconds == 4
        assert SECRET not in str(failure.value) + repr(failure.value)


def test_rate_limited_poll_and_pending_report_are_retried_but_mutations_are_not() -> None:
    clock = Clock()
    replies = iter(
        [
            httpx.Response(
                429, json={"error": {"code": "rate_limited"}}, headers={"Retry-After": "2"}
            ),
            httpx.Response(200, json={"id": str(RUN_ID), "status": "completed"}),
            httpx.Response(
                409, json={"error": {"code": "report_not_ready"}}, headers={"Retry-After": "1"}
            ),
            httpx.Response(200, json={"run": {"status": "completed"}}),
        ]
    )

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return next(replies)

    with RemoteClient(
        "https://api.example",
        transport=httpx.MockTransport(handle),
        sleep=clock.sleep,
        clock=clock.time,
    ) as client:
        assert client.wait(RUN_ID, timeout=10)["run"]["status"] == "completed"
    assert clock.sleeps == [2, 1]


def test_wait_timeout_caps_sleep_and_does_not_cancel_run() -> None:
    clock = Clock()
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json={"id": str(RUN_ID), "status": "running", "poll_after_seconds": 20}
        )

    with (
        RemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(handle),
            sleep=clock.sleep,
            clock=clock.time,
        ) as client,
        pytest.raises(RemoteTimeout, match="not cancelled"),
    ):
        client.wait(RUN_ID, timeout=2)
    assert clock.sleeps == [2]
    assert len(requests) == 1
    assert requests[0].extensions["timeout"]["read"] <= 2


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ReadTimeout])
def test_transport_errors_are_safe_and_not_retried(failure: type[httpx.RequestError]) -> None:
    received = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal received
        received += 1
        raise failure(SECRET, request=request)

    expected = RemoteTimeout if failure is httpx.ReadTimeout else RemoteTransportError
    with RemoteClient("https://api.example", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(expected) as error:
            client.start(CONFIG)
        assert SECRET not in str(error.value)
    assert received == 1


@pytest.mark.parametrize("body", [[], None, "private", {"id": "bad"}, {"status": "queued"}])
def test_invalid_acceptance_is_not_followed_to_server_selected_urls(body: Any) -> None:
    received = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal received
        received += 1
        return httpx.Response(202, json=body, headers={"Location": "https://other.example"})

    with (
        RemoteClient("https://api.example", transport=httpx.MockTransport(handle)) as client,
        pytest.raises(RemoteProtocolError),
    ):
        client.start(CONFIG)
    assert received == 1


def test_redirect_does_not_forward_api_key_or_retry() -> None:
    urls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://other.example/secret"})

    with (
        RemoteClient(
            "https://api.example", api_key=SECRET, transport=httpx.MockTransport(handle)
        ) as client,
        pytest.raises(RemoteProtocolError),
    ):
        client.capabilities()
    assert urls == ["https://api.example/v2/capabilities"]


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@api.example",
        "https://api.example?q=secret",
        "https://api.example/#secret",
        "http://remote.example",
        "file:///tmp/secret",
        "https://api.example/\nsecret",
    ],
)
def test_unsafe_service_urls_are_rejected_before_traffic(url: str) -> None:
    with pytest.raises(ValueError):
        RemoteClient(url)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_timeout_configuration_requires_positive_finite_numbers(timeout: Any) -> None:
    with pytest.raises(ValueError):
        RemoteClient("https://api.example", request_timeout=timeout)


def test_borrowed_http_client_is_not_closed_and_prefix_is_preserved() -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"api_version": "v2"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as borrowed:
        with RemoteClient("http://127.0.0.1:8000/api", http_client=borrowed) as client:
            assert client.capabilities()["api_version"] == "v2"
        assert not borrowed.is_closed
    assert paths == ["/api/v2/capabilities"]


class OversizedBody(httpx.SyncByteStream):
    """Decoded stream chunks exercising the response limit without network traffic."""

    def __iter__(self) -> Iterator[bytes]:
        yield b"x" * 512
        yield b"x" * 513


def test_response_body_limit_and_malformed_json_have_fixed_errors() -> None:
    replies = iter(
        [
            httpx.Response(
                200, headers={"Content-Type": "application/json"}, stream=OversizedBody()
            ),
            httpx.Response(200, content=SECRET, headers={"Content-Type": "application/json"}),
        ]
    )
    with RemoteClient(
        "https://api.example",
        transport=httpx.MockTransport(lambda request: next(replies)),
        max_response_bytes=1024,
    ) as client:
        for _ in range(2):
            with pytest.raises(RemoteProtocolError) as failure:
                client.capabilities()
            assert SECRET not in str(failure.value)


def test_validation_happens_before_http_and_closed_client_is_unusable() -> None:
    calls: list[httpx.Request] = []
    client = RemoteClient(
        "https://api.example", transport=httpx.MockTransport(lambda request: calls.append(request))
    )
    for invalid in [{}, {"private": object()}, {"number": float("nan")}]:
        with pytest.raises(ValueError):
            client.start(invalid)
    with pytest.raises(ValueError):
        client.report(RUN_ID, limit=101)
    with pytest.raises(ValueError):
        client.start(CONFIG, idempotency_key="bad\r\nkey")
    assert not calls
    client.close()
    client.close()
    with pytest.raises(RuntimeError):
        client.capabilities()


def test_typed_configuration_and_ignored_server_links_keep_one_service_origin() -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(str(request.url))
        assert request.url.host == "api.example"
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "id": str(RUN_ID),
                    "status": "queued",
                    "links": {"status": f"https://other.example/{SECRET}"},
                },
            )
        if request.url.path.endswith("/result"):
            return httpx.Response(200, json={"id": str(RUN_ID), "status": "completed"})
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "running"})

    with RemoteClient(
        "https://api.example/prefix", api_key=SECRET, transport=httpx.MockTransport(handle)
    ) as client:
        run = client.start(RunCreate.model_validate(CONFIG))
        assert run.status()["status"] == "running"
        assert run.result()["status"] == "completed"
        assert run.report_url == f"https://api.example/prefix/reports/?run={RUN_ID}"
    assert paths == [
        "https://api.example/prefix/v2/runs",
        f"https://api.example/prefix/v2/runs/{RUN_ID}",
        f"https://api.example/prefix/v2/runs/{RUN_ID}/result",
    ]


@pytest.mark.parametrize("operation", ["start", "cancel"])
def test_rate_limited_mutations_are_sent_only_once(operation: str) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            429, json={"error": {"code": "rate_limited"}}, headers={"Retry-After": "1"}
        )

    with (
        RemoteClient("https://api.example", transport=httpx.MockTransport(handle)) as client,
        pytest.raises(RemoteRateLimitError),
    ):
        if operation == "start":
            client.start(CONFIG)
        else:
            client.cancel(RUN_ID)
    assert len(requests) == 1
    assert requests[0].method == "POST"


@pytest.mark.parametrize(
    "body",
    [
        {"id": str(RUN_ID), "status": []},
        {"id": str(RUN_ID), "status": SECRET},
        {"id": "3ce77d6c-80e7-48d8-b3d2-5024e368a4b0", "status": "completed"},
    ],
)
def test_invalid_status_and_cross_run_identity_are_fixed_protocol_errors(body: Any) -> None:
    with (
        RemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
        ) as client,
        pytest.raises(RemoteProtocolError) as error,
    ):
        client.status(RUN_ID)
    assert SECRET not in str(error.value)


def test_request_time_consumes_total_wait_deadline_before_any_report_request() -> None:
    clock = Clock()
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        clock.now += 2
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "completed"})

    with (
        RemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(handle),
            clock=clock.time,
            sleep=clock.sleep,
        ) as client,
        pytest.raises(RemoteTimeout),
    ):
        client.wait(RUN_ID, timeout=1)
    assert len(requests) == 1
    assert requests[0].extensions["timeout"]["read"] == 1


def test_direct_target_urls_are_rejected_locally_before_any_http() -> None:
    with (
        RemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(lambda request: pytest.fail("Invalid schema sent HTTP")),
        ) as client,
        pytest.raises(ValueError),
    ):
        client.start({**CONFIG, "target": {"url": "https://agent.example/chat"}})
