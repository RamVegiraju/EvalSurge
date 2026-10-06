# ADR 0007: Store-bound MLflow experiment navigation

Status: proposed; maintainer review required.

## Context and assumptions

Reports need drill-down into original MLflow evidence without conflating a model
provider with a tracking destination. Existing trace scope authorizes at most ten
experiments; native evaluation already knows its actual experiment. At most twenty
links are returned. Load, sampling, trace budgets, and provider spend are unchanged.

## Decision

Add optional `mlflow_experiments` to report JSON with recorded experiment IDs, UI
URLs, and trace/evaluation scopes. Native evaluation records its already-known
experiment ID alongside its run ID. Report reads make no MLflow/SDK/network lookup.
Trace destinations come from the frozen plan; evaluation destinations come from
its frozen tracking store, not registered-scorer registry experiments.

HTTP(S) stores default to their tracking base. Local/file and Databricks stores
require operator-owned `BENCHMARK_MLFLOW_UI_URL`, which applies only when the current
tracking URI exactly matches the frozen store. OSS routes use `/#/experiments/`;
Databricks routes use `/ml/experiments/`, matching the installed MLflow client.
UI paths and reverse-proxy prefixes are preserved.

The operator remains responsible for pointing the UI at that store. UI placement
is presentation configuration, not a frozen evaluation-semantic input: changing
it can change navigation, never recorded scores, measurement, or judge routing.
Multiple separately hosted non-HTTP stores require a future explicit store-to-UI
map rather than guessing from credential profiles.

## Failures and trust

Reject credentials, queries/fragments on bases, unsafe schemes, ambiguous URLs,
invalid IDs, and remote plain HTTP. The browser revalidates links, renders text
without HTML injection, and uses `noopener noreferrer` plus `no-referrer`.
Authentication keys are not sent to the UI. Missing/unsafe configuration omits a
link without changing run status or triggering remote work. MLflow authorization
and protected full-trace content remain separate from sanitized profiling.

## Compatibility and verification

The report field defaults empty; historical run/plan files are not rewritten and
unknown historical evaluation experiments are not invented. Public clients gain
an additive response field, with no request or frozen-plan/hash migration.
Test store/profile mismatches, prefixes, bounds, unsafe URLs, no forwarded keys,
legacy rendering, native evaluation experiment identity, and authenticated REST
report retrieval. Update the OpenAPI snapshot and packaged assets.
