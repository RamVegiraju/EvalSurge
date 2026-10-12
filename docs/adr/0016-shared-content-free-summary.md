# ADR 0016: Shared content-free result summary

- Status: Proposed; designated maintainer review required before release
- Date: 2026-10-11
- Scope: Additive presentation API only; no execution/request changes

## Context and assumptions

Python and notebook callers currently receive typed v2 results and reports, while
the CLI owns a separate useful plain-text metric summary. Teaching JSON inspection
as the primary Python experience obscures independent lifecycle, performance,
quality and evidence outcomes. No request concurrency, provider budget, journal,
timing definition or load engine changes are needed to reuse this presentation.

Results have up to ten selected scorer criteria. Report request payloads may be
large and contain protected prompts, responses, references and rationales. Summary
rendering must not serialize these rows or access credentials/tracking resources.

## Decision and data flow

Expose `evalsurge.format_summary(result_or_report)` returning plain text. It accepts
the existing typed v2 `Result`/`Report`; legacy result/report dictionaries remain
supported for CLI compatibility. Python and notebooks call
`print(format_summary(run.result()))`. The CLI delegates its default text output
to the same renderer; explicit `--json` behavior remains unchanged.

Caller-owned DTO → bounded metadata projection → plain-text string. There is no
network, file, target, judge, tracking, OAuth or subprocess work. Typed reports
project `run` only; request records, preflight answer data and assessment rationales
are not serialized. The base client installation remains dependency-light.

The summary retains successful-only latency/answer-text TTFT coverage, attempt
counts/error rate, unknown-versus-zero usage, throughput including drain and the
single-load-level capacity qualification. Journal wait observations remain separate
and overlapping; degraded/unknown health is never an accuracy certification.
Scorer execution, selected/attempted/scored/error counts and boolean pass rates
remain distinct from lifecycle success or a CI threshold.

## Trust, failure modes and bottlenecks

Only fixed lifecycle/phase/evidence states, finite numeric observations and bounded
public scorer identifiers are emitted. Invalid/control-character labels become
unknown. Raw error/guidance text, run names, request IDs, hosts, paths, links,
provider model settings, rationales and protected evidence are omitted. Legacy
malformed or missing fields stay unknown/unavailable; unsupported top-level types
raise a fixed `TypeError` without their representations. Formatting does not mutate
the DTO, make a benchmark call or change the command exit code.

Rendering costs are bounded by fixed metric fields plus at most ten displayed
criteria. Numeric health observations cannot establish whether a generator is
unsaturated. Unknown timing coverage must never be promoted into zero or health.

## Compatibility and trade-offs

This is additive: no v1/v2 wire/schema, SDK execution, metrics arithmetic or
credential ownership changes. Existing CLI text labels/qualifications are retained
and extended with phase and judge error coverage. CLI text is human presentation,
not a stable machine format; `--json` remains the scripting interface.

A safe summary intentionally omits detailed prompts/rationales/provider errors and
arbitrary display labels. Callers retain the original typed result/report for
protected, explicit inspection. This is a convenience renderer, not another run
handle, report format, quality gate or capacity-certification interface.

## Verification

Pure presentation tests compare typed/dictionary/CLI output, preserve input data,
reject nonfinite observations and unsafe labels, distinguish unavailable/zero,
check error/evidence/generator qualifications and import dependency isolation.
These checks make no inference calls and are not real-model validation.
