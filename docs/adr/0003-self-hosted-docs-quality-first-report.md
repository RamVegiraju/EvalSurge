# ADR 0003: Self-hosted docs and a quality-first report

- Date: October 4, 2026
- Status: Implemented locally; pending maintainer and visual review
- Review owner: repository maintainer

## Context and assumptions

The report should make suggested judges and their actual evaluation outcomes easy
to inspect before latency detail. The existing `/docs` HTML returned 200, but its
CDN scripts and inline Swagger initializer conflicted with the global same-origin
script CSP. A successful HTTP response did not establish usable documentation.

Retain the local single-tenant pipeline and current limits. Report requests fetch
25 profiles per page (API maximum 100); profiles have bounded span counts. No new
provider calls, target traffic, plan mutation, or paid evaluation is introduced.
Two unmodified Swagger assets add approximately 1.77 MB before compression.

## Decision and data flow

1. Disable FastAPI's CDN-backed default documentation routes. Mount a public,
   data-free Swagger shell and pinned, licensed assets at `/docs/`.
2. Initialize Swagger from an external same-origin script. Resolve the schema
   relative to the docs URL, disable remote validation and persistent authorization.
   Preserve the existing CSP and normal API-operation authentication.
3. Redirect `/redoc` to the supported docs UI. Do not leave another broken default
   viewer or introduce a second bundle.
4. Keep authenticated report JSON and text-only DOM updates. Style the report with
   dark panels, muted text, violet accents, responsive grids, and explicit labels.
5. Present frozen judge suggestions, rationale, evidence fields, pre-load case
   readiness, and catalog/registered versions separately from captured-answer
   eligibility, selected/scored counts, Boolean rates, native metrics, and errors.
6. Keep performance, trace occupancy, heatmaps, and independent phase outcomes.
   Default waterfalls to non-orchestration operations with no direct child of the
   same category; fall back to all spans if none qualify. “Show all spans” is
   reversible. Never change persisted spans or recompute attribution in this view.
   Hotspot cards prioritize non-orchestration operations, falling back to all
   categories when necessary; the complete summary remains in report JSON.

## Boundaries and failure modes

- Docs/schema are public metadata, not access to run data. Keys entered into
  Swagger/report controls remain in that page's memory, not URL/history/storage.
- The docs require browser JavaScript, but not a CDN. Asset absence or hash drift
  fails tests/wheel verification rather than prompting a permissive CSP fallback.
- Upstream assets are executable third-party code. Immutable commit/Git blob and
  SHA-256 verification plus a license record preserve provenance, not independent
  security assurance. Review upstream fixes weekly; vendoring is not covered by
  Python dependency automation.
- A failed/invalid report refresh hides stale run data. Controls serialize page
  fetches to prevent overlapping requests from replacing newer evidence.
- Missing counts/assessments remain unknown. Zero is a valid quality rate; partial
  assessments and missing references are not passes. Numeric custom scores do not
  imply a Boolean pass rate. LLM suggestions do not imply human approval.
- Filtering enclosing spans improves readability but can hide useful nesting.
  Label the view and retain all-span access. Inclusive bars, duplicate instrumentation,
  and parallel occupancy do not prove causal bottlenecks or independent concurrency.

## Trade-offs and compatibility

Vendoring avoids a runtime CDN dependency and weakening the global CSP, at the
cost of a larger wheel and explicit asset maintenance. Vanilla JS keeps the OSS
API simple; Node.js is only required for development contract tests. Controlled
DOM tests verify rendering/data/interaction semantics, not browser layout or
complete accessibility. Human desktop/mobile review remains necessary.

The `/v1` JSON and frozen plan contracts are unchanged. `/docs` now redirects to
canonical `/docs/`; `/redoc` intentionally becomes an alias. Judge selection and
load/evaluation semantics are unchanged. Bounded rendering is linear in page
profiles/spans plus judge results; it does not address large journal/history
storage. Shared-hosting gates remain unchanged.

## Verification and guidance

Reproduce the inline-script/CSP failure before fixing it. Check same-origin assets,
public docs versus authenticated operations, version hashes/licenses, external
initialization, prefix-relative URLs, text safety, zero/unknown scores, partial and
missing evaluation, registered versions, pagination, stale data, and reversible
waterfalls. Verify the packaged wheel, OpenAPI, actual frameworks, and full suite.

Follow FastAPI's official custom docs assets guidance:
https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/

Swagger UI assets/settings follow the official distribution and configuration:
https://github.com/swagger-api/swagger-ui
https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/
