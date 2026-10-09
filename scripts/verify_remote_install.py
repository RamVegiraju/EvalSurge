"""Install the built wheel with only locked base dependencies and exercise its CLI.

This creates an independent temporary uv environment, never invokes target agents,
and uses simulated EvalSurge API resource metadata, not inference completions. It
verifies real installed distributions, not only import blockers inside the full
development environment.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

CHECK = """
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import httpx
from evalsurge import (
    Acknowledgment, AssessmentOutcome, Case, EvalSurge, EvaluationOutcome,
    EvaluationPolicy, EvidenceCapabilities, EvidenceCapability, Load,
    MissingServerDependenciesError, RemoteClient, RemoteRunFailed,
    Report, RequestValidationError, Result, RunCreate, RunStatus, ScorerOutcome,
    TargetReference, TypedRemoteClient,
)
from evalsurge.cli import main

for package in ('fastapi', 'uvicorn', 'locust', 'gevent', 'mlflow', 'openai',
                'databricks-sdk', 'requests', 'python-dotenv'):
    try:
        importlib.metadata.distribution(package)
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise AssertionError('server dependency installed: ' + package)
assert 'benchmark_agents.coordinator' not in sys.modules
assert 'evalsurge.client' not in sys.modules
assert 'site-packages' in str(Path(sys.modules['evalsurge'].__file__).resolve())
assert isinstance(EvidenceCapabilities().answer_evaluation, EvidenceCapability)
assert EvidenceCapabilities().answer_evaluation.configured is None
identifier = str(UUID('00000000-0000-0000-0000-000000000042'))
body = {'target': {'connection_id': 'test-agent'}, 'cases': [{'input': {'query': 'safe'}}],
        'load': {'concurrency': 1, 'duration_seconds': 0.1, 'max_requests': 1}}
paths = []

def response(request):
    paths.append((request.method, request.url.path))
    if request.url.path == '/v2/capabilities':
        return httpx.Response(200, json={'api_version': 'v2', 'targets': []})
    if request.method == 'POST':
        assert json.loads(request.content) == body
        return httpx.Response(202, json={'id': identifier, 'status': 'queued'})
    if request.url.path.endswith('/report'):
        return httpx.Response(200, json={'run': {'id': identifier, 'status': 'completed'}})
    return httpx.Response(200, json={'id': identifier, 'status': 'completed'})

def factory(*args, **kwargs):
    return RemoteClient(*args, **kwargs, transport=httpx.MockTransport(response))

with EvalSurge.remote('http://127.0.0.1', transport=httpx.MockTransport(response)) as sdk:
    run = sdk.start(body)
    assert str(run.id) == identifier
    assert run.wait(timeout=1)['run']['status'] == 'completed'
assert main(['doctor', '--url', 'http://127.0.0.1'], client_factory=factory) == 0
with TemporaryDirectory() as directory:
    config = Path(directory) / 'case.json'
    config.write_text(json.dumps(body))
    assert main(['run', str(config), '--wait'], client_factory=factory) == 0
assert paths.count(('GET', '/v2/capabilities')) == 1
assert paths.count(('POST', '/v2/runs')) == 2

# Typed contract documents contain lifecycle/assessment metadata only. The false
# assessment below is schema evidence, not a recorded or simulated model verdict.
request_model = RunCreate(
    target=TargetReference(connection_id='test-agent'),
    cases=[Case(input={'query': 'safe'})],
    load=Load(concurrency=1, duration_seconds=0.1, max_requests=1),
)
assert request_model.evaluation.mode == 'off'
assert EvaluationPolicy().mode == 'off'
assert EvaluationOutcome().request_coverage is None
assert ScorerOutcome(scorer='correctness', status='failed').coverage is None
assert AssessmentOutcome(request_id='schema-record', status='unavailable').value is None
links = {name: '/v2/runs/' + identifier + suffix for name, suffix in (
    ('status', ''), ('result', '/result'), ('report', '/report'), ('cancel', '/cancel'),
)}
result_document = {
    'id': identifier, 'status': 'completed', 'links': links,
    'phases': {
        'planning': 'completed', 'inference': 'passed',
        'evaluation_readiness': 'passed', 'load': 'completed',
        'profiling': 'completed', 'evaluation': 'completed',
    },
    'summary': {'performance': 'complete', 'quality': 'available'},
    'preflight': {'status': 'passed'},
    'evaluation_preflight': {'status': 'passed'},
    'evaluation': {
        'status': 'completed',
        'results': [{
            'scorer': 'correctness', 'status': 'completed', 'scored': 1,
            'pass_rate': 0, 'assessments': [{
                'request_id': 'schema-record', 'status': 'failed', 'value': False,
            }],
        }],
    },
}
report_document = {
    'run': result_document,
    'profiling': {'total_requests': 0, 'traced_requests': 0, 'coverage': 0},
    'requests': [], 'offset': 0, 'limit': 25, 'total': 0,
}
typed_paths = []

def typed_response(request):
    typed_paths.append((request.method, request.url.path))
    if request.url.path.endswith('/cancel'):
        return httpx.Response(202, json={
            'id': identifier, 'status': 'cancellation_requested', 'links': links,
        })
    if request.method == 'POST':
        assert json.loads(request.content) == request_model.model_dump(
            mode='json', exclude_unset=True,
        )
        return httpx.Response(202, json={'id': identifier, 'status': 'queued', 'links': links})
    if request.url.path.endswith('/report'):
        return httpx.Response(200, json=report_document)
    if request.url.path.endswith('/result'):
        return httpx.Response(200, json=result_document)
    return httpx.Response(200, json={
        'id': identifier, 'status': 'completed', 'links': links,
        'phases': result_document['phases'], 'poll_after_seconds': 0,
    })

with EvalSurge.remote(
    'http://127.0.0.1', typed=True, transport=httpx.MockTransport(typed_response),
) as typed_sdk:
    assert isinstance(typed_sdk, TypedRemoteClient)
    typed_run = typed_sdk.start(request_model)
    assert isinstance(typed_run.status(), RunStatus)
    result_model = typed_run.result()
    assert isinstance(result_model, Result)
    assert isinstance(result_model.evaluation, EvaluationOutcome)
    assert result_model.evaluation.results[0].pass_rate == 0
    assert result_model.status == 'completed'
    assert isinstance(typed_run.report(), Report)
    waited = typed_run.wait(timeout=1)
    assert isinstance(waited, Report)
    assert waited.run.evaluation.results[0].assessments[0].value is False
    assert isinstance(typed_run.cancel(), Acknowledgment)
    assert typed_run.report_url == 'http://127.0.0.1/reports/?run=' + identifier
    count = len(typed_paths)
    try:
        typed_sdk.start({**body, 'load': {'concurrency': 0}})
    except RequestValidationError as error:
        assert 'load.concurrency' in str(error)
        assert 'safe' not in str(error)
    else:
        raise AssertionError('invalid typed request escaped validation')
    assert len(typed_paths) == count
assert typed_paths.count(('POST', '/v2/runs')) == 1
assert typed_paths.count(('POST', '/v2/runs/' + identifier + '/cancel')) == 1
failed_result = {
    **result_document, 'status': 'failed',
    'phases': {
        'planning': 'failed', 'inference': 'not_run',
        'evaluation_readiness': 'not_run', 'load': 'skipped',
        'profiling': 'skipped', 'evaluation': 'skipped',
    },
    'summary': {'performance': 'not_run', 'quality': 'unavailable',
                'evidence_gaps': ['planning_failed']},
    'preflight': {'status': 'not_run'},
    'evaluation_preflight': {'status': 'not_run'}, 'evaluation': {},
    'planning_error': {'code': 'planning_failed', 'message': 'Planning failed'},
}

def failed_response(request):
    assert request.method == 'GET'
    if request.url.path.endswith('/report'):
        return httpx.Response(200, json={**report_document, 'run': failed_result})
    return httpx.Response(200, json={
        'id': identifier, 'status': 'failed', 'links': links,
        'phases': failed_result['phases'], 'poll_after_seconds': 0,
    })

with EvalSurge.remote(
    'http://127.0.0.1', typed=True, transport=httpx.MockTransport(failed_response),
) as failed_sdk:
    try:
        failed_sdk.wait(identifier, timeout=1)
    except RemoteRunFailed as error:
        assert isinstance(error.report, Report)
        assert error.report.run.status == 'failed'
        assert 'planning_failed' in error.report.run.summary.evidence_gaps
    else:
        raise AssertionError('failed lifecycle did not retain its typed report')
assert 'fastapi' not in sys.modules
assert 'locust' not in sys.modules
for operation in (EvalSurge, EvalSurge.local, EvalSurge.local_async):
    try:
        operation()
    except MissingServerDependenciesError as exc:
        assert 'evalsurge[server]' in str(exc)
    else:
        raise AssertionError('local operation lacked install guidance')
try:
    from evalsurge import Agent
except MissingServerDependenciesError as exc:
    assert 'evalsurge[server]' in str(exc)
else:
    raise AssertionError('local export lacked install guidance')
assert 'benchmark_agents.coordinator' not in sys.modules
print('Verified isolated legacy/typed remote SDK, public models, CLI and missing-server guidance; no inference.')
"""


def verify(wheel: Path, *, offline: bool = False) -> None:
    """Install and check one wheel without installing its optional server stack.

    Args:
        wheel: Trusted locally built distribution, installed into a temporary venv.
        offline: Require cached locked artifacts; no registry or target calls.

    Raises:
        subprocess.CalledProcessError: Installation, dependency, or behavior check
            fails. Command output is installation/test output, not target content.

    The project lock supplies only base dependencies, then the wheel is installed
    without extras and checked against its actual installed metadata. The isolated
    Python uses -I outside the checkout so editable imports cannot mask failures.
    """
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="evalsurge-remote-") as directory:
        work = Path(directory)
        environment = os.environ.copy()
        environment["UV_PROJECT_ENVIRONMENT"] = str(work / "venv")
        command = [
            "uv",
            "sync",
            "--project",
            str(root),
            "--locked",
            "--no-dev",
            "--no-install-project",
            "--python",
            sys.executable,
            "--default-index",
            "https://pypi.org/simple",
        ]
        if offline:
            command.append("--offline")
        subprocess.run(command, cwd=work, env=environment, check=True, timeout=120)
        python = work / "venv" / "bin" / "python"
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel.resolve())],
            cwd=work,
            env=environment,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["uv", "pip", "check", "--python", str(python)],
            cwd=work,
            env=environment,
            check=True,
            timeout=30,
        )
        subprocess.run([str(python), "-I", "-c", CHECK], cwd=work, check=True, timeout=30)
        subprocess.run(
            [str(work / "venv" / "bin" / "evalsurge"), "--help"],
            cwd=work,
            check=True,
            timeout=30,
        )


def main() -> None:
    """Validate the built wheel; --offline reuses the preceding CI sync cache."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--wheel", type=Path)
    args = parser.parse_args()
    if args.wheel is None:
        wheels = list((Path(__file__).resolve().parents[1] / "dist").glob("evalsurge-*.whl"))
        if len(wheels) != 1:
            parser.error("Expected exactly one built wheel or an explicit --wheel path")
        args.wheel = wheels[0]
    verify(args.wheel, offline=args.offline)


if __name__ == "__main__":
    main()
