# Measurement accuracy diagnostic — October 10, 2026

EvalSurge measures a client-observed response envelope, not server-only inference
time. The initial diagnostic found small overhead for tiny captures on one laptop,
but confirmed that blocking journal I/O can delay concurrent response handling.
It does **not** establish zero observer effect or sustainable agent capacity.

## Scope and evidence

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

## Confirmed boundaries and costs

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

## Follow-up, not implemented by this diagnostic

Material timing or persistence changes require an ADR and maintainer review:

1. Add phase-scoped generator hub-lag/CPU/journal evidence and saturation gaps.
2. Design an owned bounded cooperative writer with explicit durability checkpoints.
3. Resolve App discovery before user spawning while retaining OAuth refresh and
   exact-origin guards; state explicitly where setup falls in the run window.
4. Read compact terminal metadata for status/result rather than whole captures.
5. Separate journal/auth labels and report all-dispatched latency alongside the
   existing successful-only percentiles without rewriting historical metrics.

No baseline should be subtracted from real measurements. Cloud/serverless disks,
sustained load, target/client trace-envelope attribution and steady-state runner
health remain unverified. Exact commands and protected receipt locations are in
the repository validation record; artifacts are not committed.
