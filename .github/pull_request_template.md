## Change

Describe the problem, observable behavior, and compatibility impact.

## Design

- ADR link for API/load/persistence/profiling/evaluation semantics changes, or why none is needed:
- Load assumptions, failure modes, and trust boundaries affected:
- Migration or dependency-constraint exceptions:

## Evidence

- Focused regression tests:
- Full Ruff, pytest (including agents extra), OpenAPI validation, and build results:
- Dependency audit and latest-version verification, if dependencies changed:
- Live tests: explicit workspace/profile consent, bounded request counts, results,
  and remaining gaps; no credentials or customer data:

## Review

- [ ] Documentation and OpenAPI snapshot match behavior.
- [ ] No secret/source/content leakage or fabricated evaluation evidence.
- [ ] Smoke tests are not presented as capacity, calibration, or production sign-off.
- [ ] Architecture/contract changes receive designated maintainer review.
