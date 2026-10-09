# Serverless notebook runner: current authentication blocker

Checkpoint: October 8, 2026. Live validation is paused at the user's request.
This describes observed behavior with Databricks SDK 0.146.0, not a general claim
that serverless cannot run EvalSurge or a promise of a new authentication design.

## What failed

In the selected `e2-demo-field-eng` workspace, prerequisite Job run
`526298221857181` / task `972949342784427` used serverless environment 5 and
Python 3.12.3. Driver-native runtime OAuth, exact workspace/active identity,
loopback HTTP and POSIX locking/fsync passed. An independent Python subprocess
failed runtime-OAuth initialization with `ValueError`. The check made **zero
model calls**, did not test a deployed App and retained the failed auth result
even though the diagnostic Job itself finished successfully.

EvalSurge's sole Locust engine runs in an independent worker process. The driver
being authenticated does not establish that worker authentication works. Installed
SDK runtime-OAuth source depends on notebook-injected runtime/REPL context and
token exchange; that context was not established in the subprocess. The saved
safe exception class does not prove a more specific hidden provider error.

There is also a public configuration boundary: `Agent.databricks_app(...)`
currently takes an explicitly selected **profile**, not a notebook-native
`WorkspaceClient`. The existing resolver rejects ambient destination/identity
overrides and requires the SDK's independently refreshable OAuth credential
provider. Neither naming a laptop profile in a notebook nor receiving a driver
bearer token makes it portable to a new worker.

## Three different API topologies

| Notebook's role | Where target load originates | Effect on this blocker |
| --- | --- | --- |
| HTTP client of a separately hosted EvalSurge API | API host's Locust worker | The API operator owns target authentication. Notebook runtime OAuth is not used by that target worker. This is remote submission, not notebook load generation. |
| Host of FastAPI and Locust | Notebook-owned Locust subprocess | Loopback was verified, but starting FastAPI does not repair the independent worker's App OAuth. Notebook lifetime/public ingress/durability are separate unverified concerns. |
| Direct Python EvalSurge runner | Notebook-owned Locust subprocess | This is the intended serverless sample, with the agent remaining in its deployed App. Worker-portable authentication is still a gate. |

Serverless is a **load-generator location**, never a third agent-hosting option
in this milestone. The two target choices remain a separately hosted HTTP agent
and an agent deployed in Databricks Apps.

## What a proper fix needs next

Before live notebook→App validation, review and record an operator-owned OAuth
contract that can independently authenticate and refresh in both the notebook
driver and Locust worker. Bind it to the exact workspace, identity and App;
keep credentials/reference configuration outside `RunCreate`; preserve safe
errors and conflicting-selector rejection. This is a material authentication
change requiring an ADR and designated maintainer review, not an environment-
variable workaround already implemented by this checkpoint.

First verify both processes without inference, and verify the selected profile's
workspace before App discovery in the prepared harness. Then recheck deployed
readiness and obtain a resumed bounded traffic lease: initially one excluded
probe plus one measured call, concurrency one, evaluation off. Validate direct
and loopback-API lifecycle/cancellation/report cleanup separately before widening
coverage. Classic compute remains explicitly out of scope.

Do not copy notebook tokens, laptop OAuth caches or profiles, remove the override
guards, add a forwarding proxy, or create a new service principal/secret without
the corresponding reviewed design and user authorization. Merely submitting to
an external API is a valid different journey, not proof of notebook-generated load.

## Source and evidence pointers

- [`evalsurge/client.py`](../evalsurge/client.py): public profile-only App binding.
- [`benchmark_agents/target_resolver.py`](../benchmark_agents/target_resolver.py):
  conflicting-selector rejection and independently refreshable OAuth resolution.
- Installed SDK 0.146.0 `credentials_provider.py` and runtime authentication source:
  `runtime_oauth`, notebook runtime context and `PATOAuthTokenExchange` boundary.
- [`serverless_prerequisites.py`](../scripts/validation/serverless_prerequisites.py):
  separate driver/subprocess checks, with no model inference.
- [`serverless_runner_app_target.py`](../scripts/validation/serverless_runner_app_target.py):
  prepared, authentication-blocked harness; not evidence of a passed live journey.
- Protected receipt:
  `/private/tmp/evalsurge-serverless-prereq2-20261008.vyqPKE/receipt.json`.
- [Hosted-journey evidence](HOSTED_JOURNEY_VALIDATION.md) and
  [session handoff](SESSION_HANDOFF.md) preserve completed and blocked coverage.
