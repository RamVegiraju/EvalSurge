"""Install the built wheel with only locked base dependencies and exercise its CLI.

This creates an independent temporary uv environment, never invokes target agents,
and uses controlled HTTP transports. It verifies real installed distributions, not
only import blockers inside the full development environment.
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
from evalsurge import EvalSurge, MissingServerDependenciesError, RemoteClient
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
for operation in (EvalSurge.local, EvalSurge.local_async):
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
print('Verified isolated remote SDK/CLI and missing-server guidance.')
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
