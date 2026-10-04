---
name: evalsurge-verification
description: Debug EvalSurge failures and verify behavioral or dependency changes using regression tests, actual framework integrations, native MLflow evidence, API contracts, and built artifacts.
metadata:
  version: "1.0.0"
---

# EvalSurge debugging and verification

Read root `AGENTS.md`, `docs/CODE_GUIDE.md`, and `VALIDATION.md`.

- Reproduce the smallest observable failure before changing code. For agent behavior,
  inspect correlated spans and assessments; for transport failures, inspect safe
  error classes, phase status, timeout/retry settings, and durable attempt records.
- Identify the violated invariant and root cause. Add a regression that fails for
  that behavior; avoid assertions that merely match documentation wording.
- Preserve earlier working-tree changes and failure evidence. Never fix an unrelated
  failing test to make the requested change look successful.
- Verify with the actual LangGraph graph/OpenAI Runner and native MLflow API at
  controlled provider boundaries. Do not replace the frameworks with mocks.
- Test focused behavior during implementation, then run the full validation commands
  in `AGENTS.md` with the `agents` extra so framework tests cannot silently skip.
- For dependency changes, follow `docs/DEPENDENCIES.md`; verify supported signatures,
  async streaming completion, memory isolation, scorer serialization, and rubric drift.
- Build and check the wheel's packaged report assets. OpenAPI snapshot equality and
  schema validation are distinct from behavioral/compatibility tests; perform both.
- Record exact commands, dates, versions, results, warnings, and limitations in
  `VALIDATION.md`. A failed paid run stays failed, even if a later smoke test passes.

Live tests require an explicitly authorized profile, bounded traffic/spend, and
stopping conditions. Do not repeat paid calls just to hide a connectivity failure.
Never claim sustainable capacity, judge calibration, remote CI success, or browser
verification from evidence that does not establish it.
