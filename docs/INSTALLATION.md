# Installing EvalSurge

Direct Python execution is the default user journey. Install the `local` extra
and generate traffic on the Python caller's machine, targeting a separate HTTP
agent or deployed Databricks App. No EvalSurge API server is required.
The existing `server` extra is a compatibility alias for the same execution
dependencies; neither installation starts a server. The base package is
deliberately smaller and supports remote submission rather than generating load.
An agent framework is not required by the benchmark runner: it calls an HTTP
endpoint or a selected deployed Databricks App.

Use Python 3.11+ on Linux or macOS and a dedicated environment. This guide uses a
reviewed build artifact; it does not assert that this alpha is published on PyPI.
Replace the wheel filename with the artifact you actually received.

The current source snapshot is `0.2.1.dev2026101203`, a PEP 440 development
snapshot rather than a stable release. The project metadata and lock identify
the same version; this demo label does not upgrade any dependency or establish
publication on a package index.
This snapshot retains the `local` installation alias and adds independent
load-only trace readiness, CLI lifecycle progress, and bounded rereads when exact
trace correlation metadata has not yet become visible. Its build, installation,
and real-model checks used this exact artifact:

```text
evalsurge-0.2.1.dev2026101203-py3-none-any.whl
SHA256 1b46d96185afc7225faf6254db1181b9e023525bb67c0cb714ce948ea5b1d20f
```

Fresh isolated **uv base/local/server installs** outside the checkout passed on
macOS using the unchanged locked hashes from the explicitly approved source's
artifact cache. Installed imports, SDK lifecycle setup, packaged assets, dependency
checks and CLI/sample help made zero inference, target or authentication calls.
This is not public-PyPI publication, Linux/App installation or newest-compatible
dependency-resolution evidence.

The installed wheel then passed both synchronous and asynchronous trace-export
variants of the [multi-tool sample](../examples/journeys/multitool_heatmap/README.md)
against a separate loopback-hosted LangGraph agent using actual
`system.ai.gpt-oss-120b` Responses inference. Each run used one excluded probe and
four measured attempts, with four measured successes, zero errors and complete
measured trace coverage. Five users were configured; only four could be active
under that request cap. There were ten actual model calls total, no judges or
fallback completions, and both agent processes shut down cleanly. The tools use
disclosed synthetic documents and computation, not stubbed model answers.
These tiny runs do not establish sustainable capacity, zero observer effect,
fresh App deployment, governed trace collection or browser visual verification.
See [the exact validation record](../VALIDATION.md) for retained run IDs, outcomes
and remaining gates. Earlier wheel passes remain separate evidence.

## Historical installation-alias artifact

The earlier `0.2.1.dev2026101202` installation-alias wheel passed fresh isolated
**pip base/local/server installs** outside the checkout
on macOS, using required dependency hashes through the approved package source:

```text
evalsurge-0.2.1.dev2026101202-py3-none-any.whl
SHA256 a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285
```

Imports, request construction, CLI/sample help and dependency checks made zero
agent/model calls. Four separately bounded real-model smokes then passed from
the installed runner against LangGraph/OpenAI Agents, each over local HTTP or
an existing deployed agent App. These validate neither public-index publication,
newest-compatible resolution, Linux/runner-App installation nor current public
template deployment. Private install provenance is retained under
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/pip-reviewed-install/`;
see [the exact live evidence](LIVE_MATRIX_RESULTS.md). Earlier wheels and their
receipts remain unchanged.
The October 12 workspace-ID repair was separately frozen in
`0.2.1.dev2026101201`; the retained `0.2.1.dev2026101101` wheel lacks that repair.
The historical October 11 local real-model smokes used `0.2.1.dev20261011`, not either
native-auth build or this installation-alias snapshot.

## Direct Python or local CLI

```bash
python3 -m venv .venv
.venv/bin/python -m pip install './evalsurge-0.2.1.dev2026101203-py3-none-any.whl[local]'
.venv/bin/python -c 'from evalsurge import Agent, EvalSurge, RunCreate; print("Direct SDK imports available")'
.venv/bin/evalsurge --help
```

If you prefer uv, the equivalent installation is:

```bash
uv venv --python 3.12
uv pip install './evalsurge-0.2.1.dev2026101203-py3-none-any.whl[local]'
uv run --no-project python -c 'from evalsurge import Agent, EvalSurge, RunCreate; print("Direct SDK imports available")'
uv run --no-project evalsurge --help
```

Use a package source authorized for your environment. These commands do not
assert public package-index publication or bypass organization registry policy.
`[local]` and `[server]` select the same dependencies; the clearer name does not
add a different load engine or change where requests originate.

No source checkout, separately selected development group, API process or
agent-framework installation is needed to run the installed SDK. The locked
Locust release includes `pytest` as a transitive runtime dependency; that is not
an installation of EvalSurge's development group. The wheel includes the Locust entrypoint, report
assets and optional self-hosted API documentation assets. Import success does not
verify target authentication, deployment readiness, model availability or load
capacity.

The short install commands resolve the wheel's compatible dependency ranges.
The recorded reproducible demo checks instead install the exact versions and
artifact hashes exported from `uv.lock` through the explicitly approved source.
These are different evidence boundaries; a range-based install is not a locked
release verification.

Follow the [direct Python guide](PYTHON_API.md) to bind `Agent.http(...)` or
`Agent.databricks_app(...)`, provide a v2 request and inspect its typed report.
Credentials and Databricks profiles belong to the target/operator configuration,
not the benchmark request. Laptop App runs use an explicitly selected OAuth
profile and separately approved traffic. The deployed App hosts the agent; local
Python still owns load generation, evaluation and report retrieval. Installing
EvalSurge on the target App is not required. Examples that run EvalSurge inside
an App or notebook are separately gated and are not prerequisites for either local journey.

The local CLI can use the same v2 JSON request with operator settings:

```bash
.venv/bin/evalsurge doctor --local --settings operator.toml
.venv/bin/evalsurge run request.json --local --settings operator.toml --wait
```

Add `--progress` for live phase updates, or `--no-progress` to suppress automatic
interactive updates. [CLI progress](CLI_PROGRESS.md) goes to stderr and leaves
JSON stdout clean; it does not enable judges or tracing.

`doctor` does not invoke the agent or a judge. Use JSON for dependency-minimal
configuration; YAML requires optional PyYAML. Avoid treating a completed lifecycle
as a passing quality check, and remember that evaluation is off by default.

## App-based load generators: prepared, installation blocked

The [private runner-App sample](../examples/journeys/app_runner/README.md) is
retained historical/prepared work, not established by the fresh local installation
passes. The dedicated runner App is a separate package installation/load-generation
environment from the target agent App. Notebook work is deferred; testing an
agent App from local Python needs neither a notebook nor an API server.

This template is prepared, disabled and **not live-validated**. On October 12,
the disabled runtime deployment failed during dependency installation, before
startup or authentication. A separate zero-inference diagnostic established
Python 3.11.17 and HTTP **403** from the approved package index in the App.
The same pinned package is advertised to the laptop; registry/platform access
must be resolved before retrying the complete hash-pinned install. A successful
stdlib diagnostic deployment is not an EvalSurge installation or benchmark.
Native App-runtime authentication explicitly binds
the runner's injected service principal to the configured workspace and target
resource. Protected artifacts require an exact private schema/volume and access
policy within the selected `ram_artifacts` catalog. Reviewed artifact/source,
permissions, deployment and bounded real-model tests remain separate gates.
The October 12 ADR 0019 workspace-ID amendment also requires explicit maintainer
acceptance before deployment of the repaired runtime. See [the current
checkpoint](SESSION_HANDOFF.md); retained failure logs are private, not package
contents. No public-registry fallback is authorized.

## Optional remote submission only

```bash
uv venv --python 3.12
uv pip install ./evalsurge-0.2.1.dev2026101203-py3-none-any.whl
uv run --no-project python -c 'from evalsurge import EvalSurge, RunCreate; print("Remote SDK imports available")'
```

The base install includes HTTPX/Pydantic and public request/result models, without
Locust, MLflow or the Databricks SDK. `EvalSurge.remote(..., typed=True)` uses the
same v2 request models. Its load originates at the API host, not at this client.
Trying direct execution with only the base install gives an explicit
`evalsurge[local]` installation message that also names the compatible
`evalsurge[server]` option.

`agents` adds the server dependencies plus LangGraph/OpenAI Agents dependencies
for the repository examples. It does not install the example source files, is
not a framework allowlist and does not add CrewAI.
Customer-hosted agents own their framework/model dependencies separately.

## Verification boundaries

For a repository build, these checks inspect archives and install the actual wheel
into separate fresh base/local/server environments outside the checkout:

```bash
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_install.py --offline
```

The archive gate also parses bundled internal imports, including imports inside
runtime branches, to reject missing packaged modules without executing them or
displaying source. External optional dependencies and dynamically selected code
still need the installed execution checks; a static scan alone is not a runtime pass.

The install check uses the current lock's dependency versions/hashes and cached
authentic artifacts. It makes
zero agent/model/cloud calls: the server check opens/closes empty SDK contexts and
asks native Locust to list its installed user class without starting a benchmark.
Each environment also imports the packaged calibration/serverless helpers without
authentication, target discovery or cloud calls. The installed serverless helper's
request and budget declarations are checked, not executed.
Each also executes the packaged retrieval-consistency helper and public summary
renderer on schema-only cancelled DTOs. Those values are not substituted agent
completions or successful benchmark evidence; they test installed presentation
branches and private-field suppression without a run or model call.
The actual installed distribution version must match the packaged public
`evalsurge.__version__`; matching editable-checkout metadata is not sufficient.
It verifies neither successful real inference nor timing accuracy. It is not a
published-package download, newest-dependency resolution or every-platform install
matrix. `--offline` needs the locked dependency cache populated first.

If that cache is incomplete, an operator can explicitly select an approved package
source with `scripts/verify_install.py --dependency-index "$APPROVED_PACKAGE_INDEX"`.
That path exports unchanged versions and hashes from the lock, enforces
`--require-hashes`, and keeps installation diagnostics private. An approved
mirror-backed pass is not a public-PyPI clean install, and it must never rewrite
lock/cache origins to claim otherwise. `--evidence-dir` retains private diagnostics
and a value-free provenance receipt in a newly selected protected directory.
The install regressions keep cached/offline installation as their default. An
authorized maintainer may explicitly supply `EVALSURGE_INSTALL_CHECK_INDEX` for a
hash-pinned approved-source run; missing cache prerequisites are failures, not
silent skips or a reason to change versions.

The default verifier uses uv. To verify pip independently after freezing the
wheel, select the `local` surface and an explicitly approved dependency source:

```bash
uv run --frozen --no-sync python scripts/verify_install.py --surface local \
  --installer pip --dependency-index "$APPROVED_PACKAGE_INDEX" \
  --wheel /absolute/path/evalsurge-0.2.1.dev2026101203-py3-none-any.whl \
  --evidence-dir /absolute/path/new-private-install-evidence
```

This creates a fresh stdlib virtual environment, installs the hash-pinned local
dependency closure through pip, installs the exact wheel with its selected extra
without re-resolving dependencies, and runs pip's dependency check and the same
installed-package checks. It requires approved-source access; it does not borrow
uv's cache as a pip cache, invoke an agent, or establish public-index availability.

For the separately disclosed NON-agent timing boundary, add `--timing-only` to
the install check. It runs four native installed Locust/storage modes against an
inert loopback endpoint: normal persistence, five-ms native disk delay, failed
START before dispatch, and failed completion persistence. With the verifier's
fixed bounds this sends at most nine timing-marker HTTP requests, zero agent/model/
cloud calls. It checks packaged worker discovery, lifecycle accounting and cleanup;
it does not certify accuracy or substitute for a live agent benchmark. The server
installation regression uses this same tiny timing check. Its artifact directory
is temporary and reclaimed after verification; stdout separates timing requests
from agent dispatches.

Notebook generator installation/validation is deferred. App-based generator
installation remains separately blocked, not validated by the local pip installs.
Retained notebook sources and their
portable-OAuth prerequisites remain in
[the historical readiness record](SERVERLESS_RUNNER_STATUS.md); local installation
success does not establish notebook support. No notebook credential is required
for the active local-runner HTTP/App-agent installation milestone.
