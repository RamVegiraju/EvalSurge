# ADR 0014: Measurement integrity and owned cooperative journal persistence

- Date: October 10, 2026
- Status: Proposed; implementation follows root design review; designated maintainer review required
- Review owner: repository maintainer; root agent coordinates integration/review
- Scope: single-owner local Locust worker, not distributed execution or capacity certification

## Context, assumptions and measured problem

ADR 0001 retains one Locust subprocess, at most 100 sequential users and 10,000
attempts, bounded inputs/outputs, durable partial evidence, and no target retries.
ADR 0005 distinguishes the runner's client envelope from agent/server timing.
Each request currently opens the journal twice and synchronously writes, flushes,
and fsyncs each start/completion event on the gevent hub thread.

The initial non-inference calibration in `docs/MEASUREMENT_ACCURACY.md` measured
small native writes for the tiny real App captures on one laptop. A controlled
blocking-storage delay nevertheless inflated other in-flight users' timing;
cooperative delay did not. It also reduced whole-window throughput. The diagnostic
is not an App/serverless disk benchmark or evidence of zero observer effect.

At current limits the run can contain 20,000 durable journal events. A bounded
queue does not bound total disk growth or replace existing request-size and
concurrency bounds. Native serialization still consumes CPU/GIL time, and disk,
CPU, transport, parser and authentication overhead remain observable limitations.

## Proposed decision and data flow

1. Each Locust worker owns one journal writer and a single persistent append-only
   file descriptor. The writer uses one actual native `gevent.threadpool.ThreadPool`
   worker, not patched `threading.Thread`, `apply_async`, or another load engine.
   Source-reviewed `ThreadPool.spawn(...).get()` delegates disk work and lets the
   owning greenlet cooperate. No worker function calls into the gevent hub.
2. One owned dispatcher greenlet services a bounded FIFO event queue. Queue
   capacity is `min(configured_concurrency, 16)`; one additional event can be in
   native processing. Put/admission and durable acknowledgments wait cooperatively.
   At most one event per sequential user is outstanding. There is no unbounded
   hidden batch or fire-and-forget completion pipeline.
3. The native writer performs JSON serialization, append, flush and **one fsync
   for each event**. There is no batching or silent durability weakening. Success
   is acknowledged only after fsync returns. A started event must be acknowledged
   before authentication, payload construction or target dispatch. Admission takes
   a shallow snapshot of lifecycle row fields so a caller interrupted while waiting
   cannot mutate the queued start; nested sample inputs/references stay immutable
   under existing worker ownership. Completion clocks and
   fields become immutable before handing that event to the writer.
4. Preserve current request-clock ownership: `sent` is captured after start
   persistence/authentication and invocation-envelope mapping, just before calling
   Requests. Requests' JSON serialization and HTTP preparation remain inside the
   client envelope; this is not an on-wire or server-only clock. Completion latency includes response
   reading, validation, Locust reporting and response closure. Freeze latency,
   lifecycle and end-offset clocks **before** completion persistence. Keep the
   request's lifecycle slot owned until that persistence finishes/fails, so an
   early `active == 0` cannot quit while unacknowledged completions remain.
5. The run window still includes startup ramp, cooperative journal waits,
   authentication and request/journal drain. Offloading removes a specific disk
   blocking mechanism, not its own per-user wait or throughput cost. No baseline
   subtraction, sustainable-capacity claim, warmup exclusion or timing-redefinition
   is introduced.
6. The writer remembers its first failure, fails remaining queued acknowledgments
   with a fixed content-free journal error and prevents new dispatch. Already
   dispatched requests drain without retries. Recoverable completed rows remain
   useful; missing starts/completions or uncertain flush never become a successful
   complete run.
7. Normal finish deterministically drains the FIFO, closes the native descriptor,
   and stops its owned dispatcher/native pool. A bounded close budget prevents
   an indefinitely blocked native fsync from hanging shutdown. A thread cannot
   safely be forcibly cancelled: uncertain drain remains failed/incomplete and
   the existing parent subprocess watchdog is the hard ownership boundary.
   The parent uses one shielded, awaited TERM/grace/KILL/reap task, so repeated
   caller cancellation cannot detach the exact owned worker during its five-second
   TERM grace. This is not supervision of arbitrary descendants or target rollback.
8. Cooperative start persistence/authentication can outlast a dispatch boundary.
   Recheck cancellation and measured-window expiry both after start acknowledgment
   and immediately before HTTP dispatch (and recheck writer failure at that final
   boundary). A stopped admitted attempt persists a nondispatched terminal record,
   releases lifecycle ownership, and counts as an attempted error; it has no HTTP
   latency or TTFT. Cancellation remains separately cancelled, not successful load.
9. A reproduced START wait of 160.77 ms incorrectly caused a 34.05 ms HTTP 200
   timing response to fail a 100 ms deadline. The gevent auth/response timeout
   already starts after durable START; its explicit completion check must use that
   same clock, not the earlier lifecycle clock. Add internal `journal_start_ms`,
   `authentication_only_ms` and `request_deadline_ms`; preserve legacy `auth_ms`
   including START and preserve HTTP latency/TTFT clocks. Disk waiting remains in
   lifecycle/window/TPS and under the parent watchdog; do not call it target timeout.
10. Auth-source construction is cooperatively single-flight in the existing measured
   user phase. Shared initialization never caches OAuth tokens: each request still
   calls the existing refresh function. This prevents simultaneous App metadata
   discovery from racing before the shared callable is assigned. Do not move setup
   outside the measured window or relax exact-profile/origin guards.

## Observational, content-free generator evidence

Raw request journals retain the existing event/row format. Add a bounded aggregate
to the worker summary and public result only through typed integration:

```json
{
  "generator_health": {
    "status": "unknown",
    "observation_window": "dispatch_and_drain",
    "hub_lag": {
      "interval_ms": 10.0,
      "count": 0,
      "mean_ms": null,
      "max_ms": null
    },
    "journal": {
      "queue_capacity": 5,
      "peak_pending": 0,
      "backpressure_events": 0,
      "writer_failures": 0,
      "started_events": 0,
      "completed_events": 0,
      "drained": false,
      "enqueue_wait_ms": {"count": 0, "mean_ms": null, "max_ms": null},
      "durable_wait_ms": {"count": 0, "mean_ms": null, "max_ms": null},
      "write_and_fsync_ms": {"count": 0, "mean_ms": null, "max_ms": null}
    },
    "limitations": [
      "Observations do not establish unsaturated runner or sustainable target capacity.",
      "CPU, memory, transport and server-only timing are not measured."
    ]
  }
}
```

- `unknown` is the normal observational status, even with small lag. There is no
  calibrated healthy/pass threshold. `degraded` is reserved for known journal
  failure or incomplete drain, not a speculative latency/capacity threshold.
- Hub lag is nonnegative wake-up lateness relative to a 10 ms monotonic sleep
  request. Observe from test start through dispatch/drain; stop before summary
  serialization. This includes scheduling/CPU/other hub work, not solely disk.
- Count/mean/max are constant-space streaming accumulators, never raw samples,
  prompts, credentials, paths, trace bodies or unbounded histograms.
- Enqueue wait spans cooperative queue admission; durable wait spans admission
  through acknowledgment. Native write/fsync time excludes FIFO wait. They
  overlap; they must not be added into request latency or server wall time.
- Pending includes queued events plus one active native event; the documented
  maximum is queue capacity plus one. Backpressure counts admissions finding a
  full queue. Event counts mean successfully fsync-acknowledged events only.
- CPU/GIL work, long authentication, parser work and response closure can still
  affect the hub. No healthy-runner assertion follows from these aggregates.

## Parent recovery and public integration

`locust_runner.run_load()` must retain writer failure/drain evidence instead of
overwriting it solely because `result.json` exists and exit code is 0/1. A failed
START can leave no row and therefore zero recovered incomplete rows; compare
worker-issued/acknowledged counts to durable recovery as well. Known writer
failure, uncertain drain, attempt-count mismatch, parent watchdog timeout or
missing results must produce `measurement_complete=false` and interrupted load,
with safe journal guidance and partial rows. Do not compare fallback parent-time
rates as completed benchmark evidence.
Parent recovery marks an existing worker observation degraded when acknowledgment
counts disagree with durable rows, preserving the original counters and never
inventing extra writer failures.

The root integrator owns strict public types, run-view projection, report/CLI
presentation and current docs. Generator observations are additive; historical
reports have unavailable/absent evidence. Existing successful-only percentile
fields and completion-vs-quality decisions remain unchanged.

All-dispatched observed client durations and explicit timeout/unknown-duration
counts are a separate additive follow-up if integration remains small. They must
identify timeout durations as right-censored and interruptions as unknown, never
blend them into a fabricated successful response percentile. They are not required
to remove the disk-blocking mechanism in this initial patch.

## Portable timing-only calibration

The installed package will expose `evalsurge.calibration.calibrate(...)` and its
native-async equivalent. This diagnostic creates a private, explicitly NON-agent
localhost endpoint; it cannot accept a customer target, profile, model or scorer.
Default and hard diagnostic bounds are at most five users, 200 attempts per normal
mode and ten dispatch seconds. A fixed 25 ms native service delay is measured
independently for each request ID. Normal and native-journal 5 ms fsync-delay modes
use the same `AgentUser`, `run_load` lifecycle and recovery. Two one-attempt native
START/completion failure probes separately check incomplete evidence; no inference
fixture, model response, paid provider or cloud resource is involved.

Use a finite private calibration-mode selector on `run_load` to select the bundled
Locust wrapper. Do not mutate asyncio's global subprocess function, caller global
environment, production clock functions or supplied credentials. The fixed wrapper
imports the production user class and only injects labeled native disk delay/fault
inside that child. It is not a second load engine or arbitrary plugin boundary.
Timing-only children inherit only a fixed runtime/locale/temp environment allowlist,
not operator configuration, provider tokens, profiles, proxy settings or tracking
destinations. Normal benchmark children retain their existing operator snapshots.
The receipt separately counts actual timing HTTP requests; zero agent/model/cloud
calls does not mean zero HTTP traffic.

Each invocation requires a fresh 0700 directory (or creates a fresh private temp
directory), retains worker journals/receipts, writes a content-free aggregate and
returns the artifact path. Cleanup owns the timing server and each worker process.
Endpoint service durations and client-minus-service differences are paired by
request ID; the difference still contains transport, parsing, scheduling and clock
sampling effects. Never subtract it from benchmark metrics, award an accuracy
certificate, impose arbitrary healthy-runner thresholds or treat timing-endpoint
RPS as agent capacity. Large capture JSON serialization still consumes CPU/GIL;
transport/decoding, authentication, interpreter scheduling and shared hardware are
remaining observer mechanisms. These observations are local to the actual runtime
and filesystem, not a universal cloud or serverless sign-off.

## Failure modes, trust and trade-offs

| Area | Choice/control | Explicit limitation |
| --- | --- | --- |
| Durability | fsync each event; ack start before dispatch | Filesystem/disk loss and parent-directory durability unchanged |
| Concurrency | FIFO queue, one native writer, cooperative waits | Disk service can still lower achieved request rate |
| Mutable data | Caller holds row unchanged through durable ack | Trusted worker ownership; no arbitrary background row mutation |
| Writer failure | Fail closed, stop new dispatch, preserve partial recovery | Dispatched agent actions cannot be rolled back |
| Hung disk | Bounded owned shutdown; parent process watchdog | Native syscall cannot be safely forcibly cancelled |
| Telemetry | Fixed-size aggregates, explicit unknown/degraded status | No CPU/memory/network calibration or capacity gates |
| Compatibility | Existing journal shape/clock fields; additive results | Strict typed clients/schema need reviewed additive update |

The journal stores protected captures under the operator-owned run directory;
new files must remain protected and must not follow untrusted links. No global
environment changes, credentials in telemetry, provider calls, source execution,
extra load engine or arbitrary plug-ins are introduced. Keep gevent imports lazy
in general storage code so lightweight remote installation remains unaffected.

## Verification and release gates

Before integration, use actual native file/thread/process/clock APIs to verify
persistent descriptor ownership, FIFO order, per-event fsync acknowledgments,
start-before-dispatch, frozen completion clocks, bounded queue/backpressure,
failure propagation, exact torn/partial recovery, bounded drain and process cleanup.
A held **native** fsync must leave another greenlet ticking; use unpatched native
thread identity/events and label injected storage delay as controlled timing.
Numeric tests may verify aggregates without any agent/LLM call. Timing-only local
calibration remains explicitly non-agent evidence. Do not run existing controlled
provider/fixture inference suites or CI without the required user exception.

Document exact commands/results and unfinished live/calibration coverage. Root
must review the draft contract before material implementation. Designated maintainer
review, schema/build verification and separately approved real-model journeys
remain release gates; no successful live run is inferred from native storage tests.

## Source references reviewed

- Installed gevent 26.9 native ThreadPool source and public
  [ThreadPool API](https://www.gevent.org/api/gevent.threadpool.html).
  Installed source establishes the behavior of the repository's pinned runtime.
- Installed Locust 2.46.6 event/HttpUser interfaces and public
  [Locust API](https://docs.locust.io/en/stable/api.html).
- ADRs 0001 and 0005; `docs/MEASUREMENT_ACCURACY.md`; current `storage.py`,
  `locustfile.py`, `runner.py` and `locust_runner.py` ownership/docstrings.
