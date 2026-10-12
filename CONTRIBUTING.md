# Contributing

Use Python 3.11+ on Linux or macOS, Node.js 22+ for report/docs contract tests, and
`uv sync --locked --extra agents --group dev`.
Run the validation commands in `AGENTS.md` before proposing a change, subject to
its real-inference/disclosure policy. Locust integration tests need localhost
sockets and spawn subprocesses. Existing offline integration tests use controlled
provider responses: disclose the exact boundary and obtain explicit approval
before running them or triggering their CI. Actual agent/inference validation
requires a real model and separately approved, bounded traffic. Static schema,
storage and formatting checks make no inference calls.

Direct Python execution is the onboarding default; an API server is optional.
The base package remains the lightweight remote client and CLI (HTTPX/Pydantic).
Direct execution uses `evalsurge[local]`; the compatible `evalsurge[server]` extra
also supplies direct execution and the optional REST server. `evalsurge[agents]`
includes that stack plus both example frameworks. Keep the existing agents/dev sync
for full development and verification. Test built-wheel remote isolation as well as
the full environment so eager imports cannot reintroduce the load stack for clients.

Keep dependencies explicit and minimal. Do not add a second load runner or provider routing framework without an architectural need. Maintain the shared streaming contract, frozen evaluation policy, evidence requirements, and separation between load and judging. Changes to timing or sampling definitions must update documentation and regression coverage.

Document nontrivial functions with Google-style docstrings covering arguments, results, relevant exceptions, ownership, and side effects. Include measurement units and distinguish lifecycle completion from a passing quality verdict. Update [the code guide](docs/CODE_GUIDE.md) when responsibility boundaries change. Endpoint docstrings use `\f` to separate public operation descriptions from implementation details.

Keep user-facing Python examples small and use the public `evalsurge` facade;
put CLI orchestration and integration harnesses in `scripts/validation/`.
Keep `examples/python_benchmark.py` as an explicitly labeled credential-free
legacy mock example, not evidence of real inference or the primary tutorial. The
LangGraph and OpenAI Agents benchmark samples should call their existing
framework endpoints and include load plus explicit relevance/correctness
evaluation with authoritative references, not duplicate agent implementations.
New examples must extend the tested inventory and end-to-end cases in
`tests/test_simple_examples.py`, not merely pass an import check. Registered-target
JSON examples also extend `tests/test_framework_request_docs.py` and, for the
controlled App boundary, `tests/test_framework_app_requests.py`. CI exercises
real Locust/framework/MLflow APIs with controlled provider responses; triggering
that CI requires the disclosure/approval described above. Paid validation stays
opt-in and its results must be reported separately.

Generate the OpenAPI snapshot with `uv run python scripts/export_openapi.py`. Document breaking changes in `docs/API_REVIEW.md`; the current 0.x API is not stable. Do not commit `.env`, tokens, profiles, benchmark outputs, SQLite databases, or real customer prompts.

Describe the problem and resulting behavior in pull requests, with validation and limitations. Live paid tests require an explicitly authorized workspace, bounded traffic, and a separate validation record. Local mock tests do not establish model quality or remote throughput.

Follow the root [engineering instructions](AGENTS.md) and focused repository skills
in `.agents/skills/`. Material public API, load-engine, persistence, profiling, or
evaluation changes require an ADR under `docs/adr/` and maintainer review; use
[ADR 0001](docs/adr/0001-local-evidence-pipeline.md) as the current boundary.
Dependency upgrades follow [the dependency policy](docs/DEPENDENCIES.md), including
official-version checks, reviewed compatibility exceptions, and audited lockfiles.

Maintainers must configure branch protection/rulesets to require the CI `test`
matrix and `security` checks, reviewed pull requests, dismissed stale approvals,
and code-owner approval. CODEOWNERS and the PR template request review but do not
enable those settings. A sole author cannot independently approve their own change;
add another authorized maintainer before claiming independent review enforcement.
