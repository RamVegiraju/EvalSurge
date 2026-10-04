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
The current mirror-backed lock is a portability gate for public release and can
also prevent Dependabot from reaching package metadata; test bot access after setup.

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

Before OSS release, regenerate with `uv lock --upgrade --default-index
https://pypi.org/simple` from an environment with authorized public-index access,
install it in clean supported-version CI, and rerun the full validation and audit.
Repeat the upstream version check; this table is a dated snapshot, not a live list.

## Primary guidance

- [uv locking and upgrades](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Supported Dependabot ecosystems](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories)
- [pip-audit usage and limitations](https://github.com/pypa/pip-audit)
- [OpenAPI specification validation](https://github.com/python-openapi/openapi-spec-validator)
- [GitHub Actions supply-chain hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
