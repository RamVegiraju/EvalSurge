---
name: evalsurge-system-design
description: Review material EvalSurge API, load-engine, persistence, profiling, or evaluation architecture changes and record their measurement semantics, failure modes, and compatibility trade-offs.
metadata:
  version: "1.0.0"
---

# EvalSurge system design

Read root `AGENTS.md`, `ARCHITECTURE.md`, and the relevant ADR under `docs/adr/`.
Use this workflow for material architecture/contract changes, not trivial edits.

- Start from the requested integration and load assumptions: cases, concurrency,
  request/token sizes, run duration, trace count, retention, and available evidence.
- Estimate request rate, journal/span storage growth, memory, and provider spend.
  Mark estimates as assumptions; measured smoke-test TPS is not a capacity target.
- Trace caller → plan → Locust → journal → correlated traces → native MLflow
  evaluation → report, including credential ownership and cancellation/recovery.
- Examine fsync/generator saturation, remote exporter lag, overlapping spans,
  stalled auth/provider/scorer transports, data retention, and admission accounting.
- For each material choice, state the optimized property, sacrificed property,
  failure/recovery behavior, and compatibility/migration impact in an ADR.
- Preserve independent load/profiling/evaluation evidence and explicit gaps.
  Endpoint-only integrations cannot produce internal timing or fabricated references.
- Consult `docs/PRODUCTION_READINESS.md` before proposing shared hosting; identify
  actual tenant/egress/worker/quota controls rather than adding hosting adapters alone.

Use official OSS interfaces and current release metadata. Request maintainer review
for the ADR and public contract changes; do not infer permission for deployment or
paid tests. The System Design Primer is a pattern reference, not repository policy:
https://github.com/donnemartin/system-design-primer
