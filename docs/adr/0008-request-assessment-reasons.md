# ADR 0008: Request-correlated assessment reasons

- Date: October 5, 2026
- Status: Implemented for the local alpha; maintainer review required
- Review owner: repository maintainer

## Context and assumptions

Aggregate pass rates cannot explain individual negative assessments. Native
MLflow already retains Feedback rationales, values, and execution errors.
Keep the existing frozen sampling budget: normally 20, at most 1,000 selected
requests per criterion, at most four catalog and ten registered criteria.
No agent reinvocation, extra judge call, or tracking query is needed.

## Decision and data flow

Captured request → selected sample → native evaluation with explicit request ID
and `evalsurge.request_id` tag → exact-tag join of result rows → persisted bounded
assessment list → authenticated Python/REST report → text-only failure table.
Do not join by prompt equality or completion order; concurrent work and repeated
queries would misattribute explanations.

Each detail includes request ID, zero-based case ID, status, scalar value preview,
optional rationale, explicit rationale truncation, and optional safe diagnostic.
Only boolean false means quality failed. Numeric/categorical values retain their
scored status without an invented quality threshold. Non-scalar values are omitted.
Missing/duplicate correlation exposes unavailable evidence, never guessed reasons.
Native errors explicitly linked to older runs are excluded.

Rationales/string previews are capped at 2,000 characters. Count is bounded by the
frozen selection budget. Worst-case rationale text is 28 million characters across
14 criteria at the maximum budget, versus 160,000 at 20 answers/four criteria;
JSON escaping/identity overhead adds more bytes. This favors complete sampled
failure explanations over compact aggregate-only reports. Assessment pagination
and stricter total report budgets remain necessary before shared hosting.

## Failures and trust

Boolean quality failure is not a readiness/execution failure and does not block
load or alter lifecycle status. Native/provider failures keep safe fixed
diagnostics. Catalog-owned error codes may select specific guidance; registered
scorer errors remain generic because arbitrary raw messages and rationales may
contain secrets. Backend batch exceptions expose safe errors for selected requests
without claiming individual verdicts that could not be recovered.

Judge rationales can quote protected inputs, answers, references, or source data.
They are evaluation evidence, not content-free telemetry or guaranteed truth.
Existing authentication/no-store, operator-owned scorers, protected artifacts,
text-only DOM, and CSP continue to apply. Do not auto-link model output, export
raw exceptions, or imply truncation is redaction. Profiles stay content-free.

## Compatibility and verification

The nested `assessments` field is additive; no request, sampling, or frozen-plan
change. Historical missing details stay missing; no automatic retrieval/re-judging.
Aggregate scores and independent phase outcomes retain their existing meaning.
Verify native catalog/registered scoring, repeated inputs, reordered results,
safe execution failures, missing evidence, JSON-safe values, size bounds, hostile
text rendering, legacy reports, both API surfaces, and packaged assets.
