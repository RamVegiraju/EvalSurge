# EvalSurge engineering instructions

Scope: this repository. Read `ARCHITECTURE.md`, `CONTRIBUTING.md`, and relevant
module docstrings before changing behavior. Preserve unrelated working-tree edits.

## Skills and design

Use the versioned skills in `.agents/skills/` when their descriptions match:
`evalsurge-system-design`, `evalsurge-verification`, and `evalsurge-trust-review`.
These are focused repository workflows, not permission to run paid workloads,
install unrelated skill packs, or change external services.

Material API, load-engine, persistence, profiling, or evaluation changes need an
ADR under `docs/adr/` and designated maintainer review. Include load assumptions,
data flow, bottlenecks, failure modes, compatibility, and explicit trade-offs.
Keep the localhost MVP simple; shared hosting requires the gates in
`docs/PRODUCTION_READINESS.md`.

## Implementation invariants

- Use `uv`, typed Python, existing Ruff conventions, and focused changes.
- Document nontrivial functions with Google-style docstrings: arguments, returns,
  exceptions, side effects, ownership, timing units, and important limitations.
- Keep one Locust load engine. Do not reinvoke targets during judging.
- Freeze evaluation plans and references; preserve per-phase outcomes and gaps.
- Separate answer-text TTFT from first-event timing. Never sum overlapping spans
  into wall time or label smoke-test throughput as sustainable capacity.
- Keep credentials, tracking destinations, connections, and scorer code operator
  owned. Static setup scans must not execute code or export raw source/secrets.
- Preserve API error envelopes, authentication, bounded inputs/pagination,
  idempotency/recovery semantics, and content-free profiling artifacts.
- Remove outdated code only after checking callers, public contracts, and tests.

## Verification and dependencies

Reproduce behavioral failures and add regression coverage. Prefer actual framework
and native MLflow integration tests with controlled provider boundaries, not mocks
of the framework itself. Run focused tests during implementation, then:

```bash
uv sync --locked --extra agents --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/export_openapi.py --check
uv run openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
```

Use the newest compatible stable dependencies after checking official release
metadata and running these checks. Keep `pyproject.toml` and `uv.lock` consistent;
never relabel mirror artifact provenance as public PyPI. Follow
`docs/DEPENDENCIES.md` for updates, audits, exceptions, and release gates.

Live validation requires explicit consent, an exact user-selected Databricks
profile, bounded traffic/spend, and a separate record. Never auto-select profiles.
Before GitHub access, check `gh auth status` and select the identity authorized for
the repository. Do not change remote repository settings without authorization.

Report actual commands/results and remaining gaps. Configured CI is not evidence
that remote CI passed; skills and CODEOWNERS do not enforce branch protection.
