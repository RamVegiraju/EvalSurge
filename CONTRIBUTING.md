# Contributing

Use Python 3.11+ on Linux or macOS and `uv sync --locked --group dev`.
Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`, and `uv build` before proposing a change. Locust integration tests need localhost sockets and spawn subprocesses. No paid credentials are needed for tests.

Keep dependencies explicit and minimal. Do not add a second load runner or provider routing framework without an architectural need. Maintain the shared streaming contract, frozen evaluation policy, evidence requirements, and separation between load and judging. Changes to timing or sampling definitions must update documentation and regression coverage.

Generate the OpenAPI snapshot with `uv run python scripts/export_openapi.py`. Document breaking changes in `docs/API_REVIEW.md`; the current 0.x API is not stable. Do not commit `.env`, tokens, profiles, benchmark outputs, SQLite databases, or real customer prompts.

Describe the problem and resulting behavior in pull requests, with validation and limitations. Live paid tests require an explicitly authorized workspace, bounded traffic, and a separate validation record. Local mock tests do not establish model quality or remote throughput.
