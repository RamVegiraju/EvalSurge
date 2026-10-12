# Measurement accuracy diagnostic — October 10, 2026

EvalSurge measures a client-observed response envelope, not server-only inference
time. The initial diagnostic found small overhead for tiny captures on one laptop,
but confirmed that blocking journal I/O can delay concurrent response handling.
It does **not** establish zero observer effect or sustainable agent capacity.

## Implemented mitigation and current evidence

[Proposed ADR 0014](adr/0014-measurement-integrity-and-journal-ownership.md)
records the current implementation. One bounded cooperative FIFO feeds one
persistent native writer. Serialization, write, flush and per-event fsync no
longer execute on Locust's hub thread. START must be durably acknowledged before
target dispatch; response clocks freeze before completion persistence. Lifecycle
ownership includes completion acknowledgment and drain. Cancellation and window
expiry are checked again after cooperative waits, immediately before dispatch.
Writer failure, uncertain drain or durable-count mismatch prevents complete
measurements and preserves partial recovered evidence.

Typed results, CLI and report UI expose content-free journal/hub observations.
`unknown` means observations do not establish unsaturated generation; `degraded`
means known journal failure or uncertain drain. Missing historical telemetry stays
unavailable. Wait timings overlap: do not sum them, add them to HTTP latency or
subtract a calibration baseline from reported metrics.

The CLI and report disclose successful timing coverage against all attempts;
timeouts and other failures do not become successful tail-latency observations.
Observed FIFO backpressure produces a generator-limited-throughput warning.
Absence of that warning is not proof that durability waits, parsing or scheduling
were negligible: the writer can limit sequential users without filling its queue.

A fresh **non-agent** calibration exercised production invocation and parent
recovery against the localhost timing instrument. Each successful mode performed
200 requests, concurrency five, a ten-second maximum dispatch window and a
one-second request deadline. The delayed mode injected native storage delay only,
not an agent/provider completion. It incurred zero agent, LLM or cloud calls.

| Current writer mode | Mean client minus server service time | p95 paired difference | Achieved requests/sec |
| --- | ---: | ---: | ---: |
| Native per-event fsync | 0.471 ms | 0.710 ms | 160.80 |
| Native writer with injected 5 ms fsync delay | 0.464 ms | 0.625 ms | 76.89 |

Both recovered 200/200 successes and 400 acknowledged events, with clean drain
and no journal failure. Native write/fsync averaged 0.074 ms; durable wait averaged
0.258 ms. With injected delay these averaged 6.278/17.248 ms respectively. The
small paired differences support removal of this disk-blocking mechanism; they
are not a precise EvalSurge-only overhead estimate or a cloud-disk comparison.
Hub wake-up lag still reached 32.270/34.396 ms in the short native/delayed windows:
source/CPU/parser/startup effects are not eliminated or attributed by this probe.

Importantly, **durability can still limit achieved throughput**. Sequential users
wait for START and completion acknowledgment, and one writer serializes events.
Moving those waits off the hub prevents peer response handling from waiting on
the same disk syscall; it does not make this a generator-independent capacity
measurement. No calibrated saturation threshold or healthy-runner verdict exists.
Batching fsync would require a separately reviewed crash/durability contract; it
is not silently enabled in this patch.

Intentional native START failure dispatched zero timing requests; completion
failure retained an interrupted row rather than the worker's in-memory success.
Both returned interrupted/incomplete/degraded results. Native regressions also
cover FIFO/backpressure, durable acknowledgment, bounded close, interrupted row
snapshots, cancellation/expiry after persistence/auth waits and safe public
projection. All calibration children and the timing endpoint were stopped.

The protected receipt is
`/private/tmp/evalsurge-measurement-integrity-final-20261010.Z2pHN3/calibration_receipt.json`.
This final calibration follows the shutdown-admission and stop-boundary repairs;
the earlier calibration receipt is preserved without being relabelled.
Exact commands and final verification counts are recorded in `VALIDATION.md`.
Fresh real-agent, App and serverless-disk validation of this implementation,
designated maintainer review and full controlled-suite approval remain gates.

## Initial diagnostic: historical scope and evidence

The diagnostic used the existing production Locust engine against a localhost
timing instrument that sleeps for 25 ms and performs no inference. This is a
non-agent timing calibration, **not** a replacement for real-agent validation.
Four short, nonrandomized modes each completed 200 timing requests at concurrency
five, with a ten-second maximum dispatch window and one-second request deadline.
No new cloud, agent, LLM or paid calls occurred. The journal-disabled and delayed
modes exist only in the private diagnostic harness; production behavior did not
change. All diagnostic Locust processes and the timing endpoint were stopped.

| Diagnostic mode | Mean client minus server service time | p95 paired difference | Achieved requests/sec |
| --- | ---: | ---: | ---: |
| Native durable journal | 0.676 ms | 1.595 ms | 165.43 |
| Journal disabled, diagnostic control | 1.419 ms | 4.448 ms | 156.42 |
| Blocking 5 ms delay per write | 22.692 ms | 34.527 ms | 69.20 |
| Cooperative 5 ms delay per write | 0.575 ms | 0.939 ms | 123.63 |

The paired difference includes transport, parsing, scheduling and instrumentation;
it does not isolate EvalSurge-only latency. The noisier journal-disabled control
was slower than native in this small trial. These windows therefore cannot support
a precise native throughput-tax estimate or statistical confidence interval.
Injected delays demonstrate sensitivity to blocking, not measured cloud-disk cost.

## Initial diagnostic: confirmed boundaries and costs

- Native Locust start/completion writes averaged 0.118/0.127 ms. Separate
  120-write microbenchmarks averaged 0.098 ms for 2 KB events, 0.341 ms for
  128 KB events and 2.126 ms for 1 MB events on laptop temporary storage.
- The request's own completion write is outside its latency clock. Another
  user's blocking write can still delay its response handling and inflate
  latency or answer-text TTFT. Native `os.fsync` was not patched by gevent.
- Cooperative waits avoid blocking peer users, but a sequential user's own
  journal wait still reduces achieved throughput. A journal redesign must
  explicitly preserve durability, interruption recovery and shutdown semantics.
- `auth_ms` currently includes the initial journal write; it is not pure
  authentication time. A read-only audit of the historical 500 real App captures
  found median/p95 0.178/0.268 ms, maximum 1,922 ms, and five samples above 100 ms.
  These cold setup observations are outside request latency but inside run TPS.
  They do not establish model latency or isolate discovery from authentication.
- Historical App completion rows averaged 776 bytes, maximum 1,005 bytes. The
  large-payload microbenchmark must not be applied to those tiny captures.
- A 21 MB/10,000-row snapshot took mean 17.50 ms to read/parse and 13.48 ms to
  deep-copy. Approximately 31 ms is the sum of separate component means, not a
  jointly measured status endpoint. Terminal reads repeat this synchronous work.
  Locust is a separate process: this risks shared CPU/disk contention and control
  responsiveness, not direct blocking of its users' event loop by API polling.
- Nearest-rank percentiles and rate arithmetic match the documented contract.
  Successful-only tails omit failed/time-out attempts; achieved TPS includes
  ramp, authentication, journal waits and drain, not a steady-state window.

The oversized single-event SSE parser stress probe was interrupted and reaped
inside the native Requests line parser. It produced no completed runtime or
streaming pass; separately bounded per-size profiling remains necessary. Blindly
increasing the read chunk size could alter TTFT and is not a verified fix.

## Packaged diagnostic — October 11, 2026

The reviewed wheel includes an explicit diagnostic, not an agent substitute:

```python
from evalsurge.calibration import calibrate_async

receipt = await calibrate_async(concurrency=5, max_requests=4, duration_seconds=1)
```

Use `calibrate(...)` in a synchronous script; use `await calibrate_async(...)` in
an active notebook/event loop. It owns an inert loopback timing endpoint and the
production Locust worker/recovery path, sends no credentials to its children and
makes zero model/agent/cloud calls. Bounds are at most five users, 200 requests per
normal mode and ten dispatch seconds per mode; two storage-fault modes use one
attempt each. Four modes deliberately test native persistence, injected native
5 ms fsync delay and failures before START/completion write.

`completed` requires successful correlated timing pairs, exact injected-fault
accounting and observed server/handler/worker cleanup. Native handlers are joined;
TERM/grace/KILL/reap and server close remain owned through repeated cancellation.
Cancellation is re-raised after retaining the protected diagnostic receipt. No
normal result may claim cleanup from an unavailable PID observation. Native
shutdown failures, abrupt interpreter loss and alternate runtimes remain limitations.

This tiny fixed payload does not validate large captures, serverless storage,
real framework inference or a universally unsaturated runner. Paired timing
includes transport/parser/scheduling costs; never subtract it from an agent run.
Fresh installed-wheel checks exercise this path independently of the checkout.

## Remaining follow-up

Material timing or persistence changes require an ADR and maintainer review:

1. Add CPU/resource evidence and calibrated generator-saturation gates. Hub-lag and
   journal aggregates are implemented, but do not establish a healthy generator.
2. Measure the current writer on cloud/serverless storage and with real agents;
   review any batching/checkpoint alternative before changing durability.
3. Resolve App discovery before user spawning while retaining OAuth refresh and
   exact-origin guards; state explicitly where setup falls in the run window.
4. Read compact terminal metadata for status/result rather than whole captures.
5. Separate journal/auth labels and report all-dispatched latency alongside the
   existing successful-only percentiles without rewriting historical metrics.

No baseline should be subtracted from real measurements. Cloud/serverless disks,
sustained load, target/client trace-envelope attribution and steady-state runner
health remain unverified. Exact commands and protected receipt locations are in
the repository validation record; artifacts are not committed.
