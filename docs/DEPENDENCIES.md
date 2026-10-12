# Dependency and release policy

Prefer the newest **compatible stable** release, not prereleases or an untested
major upgrade. `pyproject.toml` expresses supported ranges; `uv.lock` records the
exact reproducible environment. Widening a range is not proof of compatibility.

## Remote and execution dependency surfaces

The default distribution has only HTTPX and Pydantic as direct dependencies.
`evalsurge[local]` is the clearer additive installation name for direct execution;
it expands to the unchanged `[server]` dependency set. Framework dependencies
remain in the agent's own environment, not the load generator.
`evalsurge[server]` installs the existing REST/local Locust, MLflow, provider and
Databricks SDK stack; `evalsurge[agents]` includes server plus both example frameworks.
The agents extra refers to the server extra in project metadata, preserving the
existing full-development sync/audit commands. Hatchling expands this self-reference
to ordinary extra-marked requirements in built-wheel metadata.

Remote imports defer local-only modules. Tests build and install a real wheel into
a fresh base-only uv environment, assert that server distributions are absent,
exercise SDK submit/wait and CLI run/doctor through controlled HTTP transports, and
check the installed entry point and helpful missing-server errors. Run
`uv run --frozen --no-sync python scripts/verify_remote_install.py --offline` after a full
locked sync and build; CI includes this gate on every supported Python version.
This is remote-install isolation, not a published-release install or live service test.

For this October 7 packaging migration, official public-index resolution still
failed with TCP connection refused, including an approved outside-sandbox retry.
Only the editable project's dependency/extra metadata in `uv.lock` was migrated;
all registry package versions, sources, artifact URLs, hashes, and dependency graphs
were retained. `uv lock --check --offline --default-index https://pypi.org/simple`
and full agents/dev locked offline sync accepted the migrated metadata. This is a
verified metadata migration, not a fresh latest-compatible dependency resolution.

The October 12 `0.2.1.dev2026101202` update likewise changes only the editable
project version and extra metadata. All 189 non-editable package records remain
identical, including dependency graphs, hashes and registry/artifact origins.
Offline lock checking accepts 190 packages; frozen local/server hashed exports are
byte-for-byte identical. This does not establish newest-compatible dependencies
or public-index publication. Fresh pip installation evidence is recorded separately
in [validation](../VALIDATION.md).

## Update workflow

Verification is not a dependency update. In a checkout with a configured package
mirror, use `uv run --frozen --no-sync ...` for inspection/tests: `--no-sync` alone
does **not** prevent lock resolution or changes. Keep locked export/sync commands
explicit about the lock's index identity, use offline checks when appropriate and
retain approved-source install provenance separately. Never rewrite mirror URLs
into public origins or commit an unintended mirror resolution. The October 11
installation gate caught such a verification-time mutation; its failed candidates
remain private evidence, and the known baseline lock was restored with only the
deliberate project-version change before final verification.

1. Verify published versions and migration guidance using official PyPI metadata
   and upstream release notes. Record the date, interpreter, and index.
2. Run `uv lock --upgrade`, then `uv sync --locked --extra agents --group dev`.
   Include all transitive, optional, development, and build dependencies.
3. Run focused regressions, both real framework integrations, native MLflow tests,
   full Ruff/pytest, OpenAPI snapshot/schema checks, and wheel verification.
4. Audit a hashed export of the complete dependency graph with `pip-audit`.
   Review advisories and licenses; never suppress an advisory just to pass CI.
5. Document intentional upper bounds and incompatible upgrades with their reason,
   migration work, test evidence, and a next review date. Submit reviewed changes;
   never auto-merge a dependency update or blindly upgrade a major version.

```bash
uv lock --upgrade
uv sync --locked --extra agents --group dev
uv export --quiet --locked --extra agents --group dev --no-emit-project \
  --output-file artifacts/audit-requirements.txt
uv run --frozen --no-sync pip-audit --disable-pip --require-hashes \
  --progress-spinner off --vulnerability-service osv \
  --requirement artifacts/audit-requirements.txt
```

Create `artifacts/` before exporting. Hatchling is included in the development lock;
CI uses `uv build --no-build-isolation` after syncing that lock so build-backend
dependencies are reproducible and included in the audit. Ordinary isolated builds
resolve the compatible backend range separately and need release provenance checks.
The OSV audit checks package versions for known advisories and enforces hash
presence, not artifact hash validity; uv verifies downloaded artifact hashes.
Audit each supported interpreter because exported environment markers can select
different dependency versions. A clean advisory scan is not a security review.

## Automation and review

Dependabot requests weekly `uv` and GitHub Actions updates. MLflow upgrades are
grouped separately because direct catalog rubrics depend on private prompt APIs.
Major updates remain separate from compatible runtime groups. PR CI tests the
locked graph with both framework extras; Monday scheduled CI also resolves fresh
compatible dependencies and tests/audits them without modifying the main branch.
Review scheduled failures promptly and open a corrective update PR.

CI is configured for Python 3.11–3.14 on Linux; local evidence is recorded separately
in `VALIDATION.md`. GitHub actions are pinned to verified commit hashes, not mutable
major tags. Current pins are checkout v7.0.1 and setup-uv v10.2.0; the uv tool version
is 0.12.23 (official releases checked October 4, 2026).

Required checks and CODEOWNERS need repository rulesets/branch protection enabled
by a maintainer. Configuration files alone do not enforce review or prove CI passed.
A mirror-backed lock blocks public CI installation and public release.
CI checks registry and artifact origins before installation with the stdlib-only
`python3 scripts/check_ci_prerequisites.py` (Python 3.11+). Registry packages must
use public PyPI and its HTTPS artifact host; local editable packages are excluded.
This checks source suitability, not network reachability or resolver provenance.
CI explicitly uses `UV_DEFAULT_INDEX=https://pypi.org/simple` for fresh resolution;
that setting alone does not replace mirror artifact URLs already in a lockfile.

The CI test job also pins setup-node v7.0.0 to its official commit, with Node.js 24
for JavaScript report/docs contracts. Node is not an API runtime dependency.

### Vendored documentation assets

Swagger UI v5.33.1 is vendored from official commit
`cac3d136b5e37bfbe3288c8591f6f4fcf9870599` (latest stable release verified October 4,
2026; released October 1). Its Apache-2.0 license, upstream blob IDs, and SHA-256
hashes are recorded in `benchmark_agents/docs_ui/vendor/`. Documentation and wheel
tests check asset presence/integrity. GitHub Advisory Database returned no matching
`swagger-ui-dist@5.33.1` advisories on October 4; this is not an audit of all bundled
transitive JS code.

Vendored files are **not** updated by `uv` or Dependabot's Python workflow. Review
official Swagger releases/security notes during the weekly dependency review
(next: October 12, 2026), replace assets only from a verified immutable commit,
update provenance/hashes, and rerun the full verification and manual docs review.

## Current compatibility exceptions

| Package | Constraint | Reason | Next review |
| --- | --- | --- | --- |
| MLflow | `>=3.16.1,<3.17` | Private correctness/relevance/safety prompt modules and rubric hashes; verify signatures, serialization, native scoring, and tracing before widening | October 12, 2026, or the next release PR |
| Major versions | Upper bounds per package | Unverified incompatible API changes must not silently enter reproducible builds | Each weekly update PR |

LangGraph, checkpoint, and LangChain integration ranges allow their current major
series rather than unnecessarily freezing tested minors. Pre-1.0 Agents SDK
updates still require migration review and actual Runner streaming/memory tests.

The October 4 resolution also retained older transitive versions required by their
parents: Graphene/graphql-relay constrain graphql-core below 3.3; aiohttp constrains
multidict below 7; Databricks SDK constrains protobuf below 7; Pydantic pins
pydantic-core exactly; LangChain/LangSmith constrain uuid-utils below 1; Agents and
LangGraph SDK constrain websockets below 17. Upgrade/retest those parents rather
than force an inconsistent transitive graph.

## Index limitation — October 4, 2026

This is historical evidence. The mirror lock is replaced by the validated public
recovery below; fresh latest-compatible resolution remains blocked locally.

Public PyPI connections from the installer fail even outside the sandbox. The
configured Databricks mirror is reachable, but is behind upstream. Official
upstream releases confirmed today include:

| Package | Current reachable release | Official upstream stable release |
| --- | --- | --- |
| FastAPI | 0.141.1 | 0.142.2 |
| OpenAI SDK | 3.19.2 | 3.24.0 |
| OpenAI Agents SDK | 0.22.3 | 0.23.1 |

These are availability limitations, not a claim that older packages are globally
latest. A public-index offline resolution also failed because required Databricks
SDK metadata was not cached. Do not rewrite registry/download URLs or hashes to
pretend the mirror lock was resolved from public PyPI.

For the next latest-compatible update and OSS release, resolve with `uv lock --upgrade --default-index
https://pypi.org/simple` from an environment with authorized public-index access,
install it in clean supported-version CI, and rerun the full validation and audit.
Repeat the upstream version check; this table is a dated snapshot, not a live list.

### CI diagnosis — October 5, 2026

Read-only GitHub inspection confirmed runs `37311757111` (main `d83ef4a`) and
`37322866817` (docs merge on main `fb8ce89`) failed all eight Python 3.11–3.14
test/security jobs during `uv sync --locked --extra agents --group dev`.
Each download failure timed out against the configured internal registry mirror;
tests, schema/build checks, and the advisory audit did not run. This is an
installation failure, not evidence of eight code regressions or vulnerabilities.
The affected `d83ef4a` lock has 211 registry entries pointing at that mirror.

Checkout v7.0.1, setup-node v7.0.0, setup-uv v10.2.0, and uv 0.12.23 matched
official latest release metadata on October 5; the action tags matched the pinned
commit hashes. Setup steps succeeded, so changing pins or extending timeouts is
not the evidenced fix.

Dependabot PR #1 (`d81e435`) already contains public-PyPI registry sources.
Its PR run `37242520002` on October 4 passed all eight jobs, including installation,
tests, builds, and audits. That PR is based on `e245ae6`, before preflight changes;
review its dependency updates and validate against current code before applying
it. Neither the lockfile nor dependency ranges were changed by this CI diagnosis.
The early prerequisite check detects nonpublic origins; it does not repair a lock
or establish that current remote CI passes. No workflows were rerun and no remote
settings were changed.

### Adopted public-lock recovery — October 5, 2026

The exact PR #1 files were fetched through the authorized GitHub API at commit
`d81e43531ffa1f1ee6e8890304f3fa3a5a3861b2`. The lock's Git blob is
`89c0f7ad5c56629a4c27d8246eca0a22f4b366b7`; its SHA-256 is
`468ac9fe28395d9a61cc30c3248c92cf530615c24a8a06c4ff1d87aa91efc93a`.
Neither registry URLs nor artifact hashes were rewritten. PR #1 changes only
the lock; its dependency ranges, extras, development group, and build requirements
match the current project.

| Package | Mirror lock | Adopted public lock |
| --- | --- | --- |
| FastAPI | 0.141.1 | 0.142.2 |
| LangChain Core | 1.6.5 | 1.6.6 |
| LangChain OpenAI | 1.6.6 | 1.6.7 |
| OpenAI SDK | 3.19.2 | 3.22.1 |
| python-dotenv | 1.2.3 | 1.2.4 |
| Ruff | 0.16.9 | 0.16.10 |

All declared runtime/framework/development/build constraints accept the adopted lock.
MLflow, MLflow Skinny, and MLflow Tracing remain at 3.16.1, with unchanged
distribution hashes. Installed correctness, relevance, and safety private prompt
functions import and render successfully with the current callers; the combined
rubric hash is unchanged. Keep the `<3.17` exception. Initial current-code verification
against the separate public environment passed 272 tests with no skips. Final root
verification passes 277 tests with no skips, including native scoring, tracing,
serialization, both frameworks, actual Locust HTTP traffic, and storage-fault and
editable-build regressions. See `VALIDATION.md` for exact commands and scope.

`uv sync --locked --extra agents --group dev --no-install-project` installed 181
packages into a separate artifact environment on macOS/Python 3.12.13 using uv
0.11.28. The exact candidate lock hash remained unchanged. An OSV audit of its
hashed agents/dev/build export checked 181 applicable dependencies and found zero
known advisories; OSV enforces hash presence, while uv verifies artifact integrity.
This is not a security review or a current Linux matrix result.

Generated provenance, constraints, installed versions, prompt signatures, and audit
evidence are under `artifacts/ci-public-lock/`. The root `uv.lock` adopts the exact
verified file byte-for-byte after full current-code validation. CI explicitly uses
public PyPI and checks registry/artifact origins before installation. This addresses
the observed mirror-download cause; no new remote CI run or current Linux matrix is
claimed. This is a reviewed recovery graph, not a newly resolved latest graph.

### Latest-upstream gap — October 5, 2026

Fresh official GitHub stable-release metadata identifies these newer releases,
all within the existing declared ranges:

| Package | Recovery candidate | Observed upstream stable release |
| --- | --- | --- |
| OpenAI SDK | 3.22.1 | 3.24.0 |
| OpenAI Agents SDK | 0.22.3 | 0.23.1 |
| Locust | 2.46.6 | 2.46.7 |

These are release observations, not proof of package-index availability or
compatibility. Metadata for direct dependencies is saved separately from the
candidate; gevent's GitHub latest-release endpoint is stale, so its observed
26.9.0 tag is not treated as a global latest-version guarantee. No claim is made
that every transitive package is upstream-latest.

Authorized fresh resolution with unchanged ranges and explicit
`--default-index https://pypi.org/simple` failed with TCP connection refused.
Public PyPI metadata/index access remains unavailable here even though locked
`files.pythonhosted.org` artifact downloads succeeded. The generated
`artifacts/ci-public-lock/fresh-20261005/` contains the project input and failure
log, not a fresh lock or environment. Finish the reviewed upgrade workflow from
an authorized environment with working public-index access; do not disguise this
gap by rewriting the authentic candidate's URLs, hashes, or version records.

## Pre-push upstream review — October 7, 2026

Official GitHub stable-release metadata was rechecked for all 22 declared runtime,
framework, development, and build dependencies. Monorepo releases were matched to
the specific package rather than assuming a repository's generic latest release
was the package version. Gevent's latest-release endpoint remains stale; its
highest observed release tag is 26.9.0, matching the lock, not a fresh PyPI result.

Newer observed upstream releases:

| Package | Locked version | Observed upstream stable release | Disposition |
| --- | --- | --- | --- |
| [OpenAI SDK](https://github.com/openai/openai-python/releases/tag/v3.26.0) | 3.22.1 | 3.26.0 | Range permits it; controlled compatibility validation pending |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python/releases/tag/v0.23.1) | 0.22.3 | 0.23.1 | Range permits it; actual Runner/memory integration validation pending |
| [Locust](https://github.com/locustio/locust/releases/tag/2.46.7) | 2.46.6 | 2.46.7 | Range permits it; native load regression validation pending |
| [Databricks SDK](https://github.com/databricks/databricks-sdk-py/releases/tag/v0.148.0) | 0.146.0 | 0.148.0 | Range permits it; profile/auth-routing metadata and OAuth integration review pending |
| [LangChain Core](https://github.com/langchain-ai/langchain/releases/tag/langchain-core%3D%3D1.6.7) | 1.6.6 | 1.6.7 | Range permits it; framework/serialization validation pending |
| [LangGraph](https://github.com/langchain-ai/langgraph/releases/tag/1.2.14) | 1.2.12 | 1.2.14 | Range permits it; graph/streaming/memory validation pending |
| [MLflow](https://github.com/mlflow/mlflow/releases/tag/v3.17.0) | 3.16.1 | 3.17.0 | Intentionally excluded by `<3.17`; private rubric APIs/hashes require migration review |

The other declared dependencies match their observed package-specific stable
release metadata. This does not establish that every transitive dependency is
upstream-latest or that newer packages are compatible/index-accessible. Swagger UI
5.33.1, CI checkout 7.0.1, setup-node 7.0.0, setup-uv 10.2.0, and pinned uv 0.12.23
also match observed official releases. The GitHub Advisory Database returned no
matching `swagger-ui-dist@5.33.1` advisories; bundled transitive JS remains outside
that narrow query.

Direct public PyPI metadata access still fails with TCP connection refused, even
after retry outside the sandbox. The verified public lock remains unchanged;
no registry URLs, artifact URLs, hashes, or versions were relabeled. Open
[Dependabot PR #4](https://github.com/RamVegiraju/EvalSurge/pull/4) updates two
packages but is not a reviewed current full-graph upgrade and does not contain
the newest observed OpenAI version. It was inspected read-only, not merged or
otherwise changed. Finish the update workflow from an authorized public-index
environment; review these gaps by **October 12, 2026**, or the next dependency PR.

The unchanged full agents/dev/build hashed export was audited with OSV using
`pip-audit --disable-pip --require-hashes`: **181 applicable dependencies, zero
known advisories** on local Python 3.12. OSV enforces hash presence, not artifact
validity; uv retains responsibility for download hash validation. This is not a
clean-install matrix, complete license audit, or security sign-off. Evidence is
retained under ignored `artifacts/prepush-20261007/`.

## Publication metadata recheck — October 8, 2026

Official GitHub stable-release metadata was rechecked for the OpenAI SDK, OpenAI
Agents SDK, Locust and Databricks SDK. OpenAI SDK
[3.26.1](https://github.com/openai/openai-python/releases/tag/v3.26.1) and Databricks
SDK [0.149.0](https://github.com/databricks/databricks-sdk-py/releases/tag/v0.149.0)
were published October 8; the unchanged lock still contains 3.22.1 and 0.146.0.
The observed Agents 0.23.1 and Locust 2.46.7 releases remain newer than locked
0.22.3 and 2.46.6. These observations supersede only the corresponding latest-release
observations in the October 7 table; they do not change that historical audit.

The fetched Dependabot runtime branch updates Locust to 2.46.7, OpenAI to 3.24.0
and Agents to 0.23.1. It was inspected read-only, not merged: it is neither a
validated full-graph upgrade nor the newest observed OpenAI/Databricks environment.
Finish the existing compatibility/update workflow before adopting it.

The bare required `uv sync --locked --extra agents --group dev` resolved against
the ambient index configuration and rejected the unchanged lock. Explicit
`--default-index https://pypi.org/simple --offline` accepted the authentic public
lock and checked the cached agents/dev environment. No dependency metadata, source,
version or hash was rewritten for this publication. A fresh hashed export of the
unchanged agents/dev/build lock was audited with OSV: **181 applicable dependencies,
zero known advisories, no skipped packages** on local Python 3.12. Evidence is under
ignored `artifacts/prepush-20261008-audit.*`. This checks known version advisories
and hash presence, not artifact validity, licenses or other interpreters. A fresh
full-graph latest-release review and public-index clean install was not performed;
the October 12 review deadline and existing release gaps still apply.

## Publication metadata recheck — October 10, 2026

Official upstream release metadata was rechecked on October 10:

| Package | Latest stable observed | Adoption status |
| --- | --- | --- |
| OpenAI SDK | 3.28.0, published October 9 | Locked 3.22.1 remains; compatibility/update validation pending |
| OpenAI Agents SDK | 0.23.1 | Locked 0.22.3 remains; framework validation pending |
| Locust | 2.46.7 | Locked 2.46.6 remains; native load regression validation pending |
| Databricks SDK | 0.151.0, published October 10 | Locked 0.146.0 remains; auth/profile integration validation pending |
| MLflow | 3.17.0 | Deliberately excluded by `<3.17`; rubric migration review required |
| CrewAI (isolated example only) | 1.15.27, published October 9 at 22:33:44 UTC | Not a project dependency; unavailable through the approved development source |

CrewAI 1.15.26 is also absent from that approved source; 1.15.23 is visible and
resolved in an isolated preparation environment, but was not installed or run.
Availability is not evidence of compatibility, and absence is not evidence of
incompatibility. Do not bypass registry policy, install saved artifacts as an
alternative route, change global package configuration, or publish private index
provenance. See [the hosted validation record](HOSTED_JOURNEY_VALIDATION.md).

`pyproject.toml` and `uv.lock` remain unchanged for this checkpoint. These are dated
metadata observations, not validated upgrades, a fresh vulnerability audit or a
claim that the repository is dependency-current. The existing October 12 review
deadline and clean-install/compatibility gates remain in force.

## Primary guidance

- [uv locking and upgrades](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Supported Dependabot ecosystems](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories)
- [pip-audit usage and limitations](https://github.com/pypa/pip-audit)
- [OpenAPI specification validation](https://github.com/python-openapi/openapi-spec-validator)
- [GitHub Actions supply-chain hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
