# Dependency and release policy

Prefer the newest **compatible stable** release, not prereleases or an untested
major upgrade. `pyproject.toml` expresses supported ranges; `uv.lock` records the
exact reproducible environment. Widening a range is not proof of compatibility.

## Update workflow

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
uv run --no-sync pip-audit --disable-pip --require-hashes \
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
Each download failure timed out against `pypi-proxy.cloud.databricks.com`;
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

## Primary guidance

- [uv locking and upgrades](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Supported Dependabot ecosystems](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories)
- [pip-audit usage and limitations](https://github.com/pypa/pip-audit)
- [OpenAPI specification validation](https://github.com/python-openapi/openapi-spec-validator)
- [GitHub Actions supply-chain hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
