"""Validated public API contracts."""

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

RunStatus = Literal[
    "queued",
    "preflighting",
    "running",
    "profiling",
    "evaluating",
    "completed",
    "completed_with_gaps",
    "failed",
    "interrupted",
    "cancelled",
]
LoadStatus = Literal[
    "queued", "running", "completed", "failed", "interrupted", "cancelled", "skipped"
]
EvaluationStatus = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_errors",
    "completed_with_gaps",
    "no_ready_scorers",
    "needs_configuration",
    "configuration_changed",
    "failed",
    "interrupted",
    "skipped",
]


class Model(BaseModel):
    """Reject unknown top-level model fields and validate attribute assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Sample(Model):
    """One workload case and optional authoritative reference evidence."""

    inputs: dict[str, Any] = Field(
        description="For http-json, the raw nonempty object sent as the POST body. For SSE adapters, query or a nonempty messages array.",
        examples=[{"query": "Can I refund?"}],
    )
    expectations: dict[str, Any] = Field(
        default_factory=dict,
        description="Authoritative expected_response or expected_facts; never invented by the planner.",
    )


class Capability(Model):
    """An explicitly disclosed capability, not proof of runtime behavior."""

    name: str = Field(min_length=1, max_length=128, description="Public tool or memory name.")
    kind: Literal["tool", "retrieval", "memory"] = Field(
        default="tool", description="Declared capability category, not observed runtime evidence."
    )
    description: str = Field(default="", max_length=2000, description="Purpose, without secrets.")


class AgentManifest(Model):
    """Opt-in setup context for planning; source code is never executed by the API."""

    name: str = Field(min_length=1, max_length=128, description="Human-readable agent name.")
    framework: Literal["langgraph", "openai-agents"] = Field(
        description="Framework whose setup the owner discloses."
    )
    description: str = Field(default="", max_length=4000, description="Agent objective.")
    capabilities: list[Capability] = Field(
        default_factory=list, max_length=50, description="Reviewed public capability descriptions."
    )
    source: Literal["user", "static-scan"] = Field(
        default="user", description="Manifest origin; static scans still require owner review."
    )


class Evaluation(Model):
    """Evaluation criteria, optional data, and a per-scorer assessment budget."""

    description: str = Field(
        min_length=1,
        max_length=10000,
        description="Agent objective and quality criteria.",
        examples=["Answer refund questions accurately"],
    )
    samples: list[Sample] = Field(
        default_factory=list,
        max_length=1000,
        description="Optional for planning; at least one case is required for load generation.",
    )
    scorers: list[Literal["relevance", "correctness", "safety", "groundedness"]] | None = None
    agent_manifest: AgentManifest | None = Field(
        default=None, description="Opt-in, sanitized setup context; not runtime evidence."
    )
    registered_scorers: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Operator-allowlisted MLflow scorer aliases. None permits suggestions; [] disables.",
    )
    max_scored_requests: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum captured responses per ready scorer; provider retries are separately bounded.",
    )
    sampling_seed: int = Field(
        default=42,
        ge=0,
        le=2**32 - 1,
        description="Seed for deterministic sampling of the same captured request records.",
    )


class Target(Model):
    """Hosted HTTP endpoint and an optional server-owned connection reference."""

    url: HttpUrl = Field(
        description="Exact HTTP endpoint URL (SSE or JSON) authorized by server target policy.",
        examples=["http://127.0.0.1:9001/chat"],
    )
    adapter: Literal["openai-chat", "mlflow-agent-server", "http-json"] = "openai-chat"
    framework: Literal["langgraph", "openai-agents"] | None = None
    model: str = Field(
        default="agent",
        description="Model name sent only by openai-chat; ignored by mlflow-agent-server and http-json.",
    )
    request_usage: bool = Field(
        default=True,
        description="Request streamed token usage for openai-chat. Disable when the endpoint rejects stream_options; absent usage stays unknown. Ignored by mlflow-agent-server and http-json.",
    )
    connection_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class Load(Model):
    """Closed-loop users at one concurrency level; duration limits dispatch, then requests drain."""

    concurrency: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Sequential Locust users, each with at most one request in flight.",
    )
    duration_seconds: float = Field(
        default=30,
        ge=0.1,
        le=3600,
        description="Dispatch window starting at Locust test_start, including user ramp-up.",
    )
    max_requests: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Hard cap on attempted requests, including authentication failures.",
    )
    timeout_seconds: float = Field(
        default=30,
        ge=0.1,
        le=120,
        description="Per-attempt deadline covering authentication and complete response streaming.",
    )


class RunRequest(Model):
    """Benchmark inputs. Reuse plan_id to avoid invoking the planner again."""

    target: Target = Field(description="The hosted endpoint to exercise.")
    evaluation: Evaluation = Field(description="Criteria and workload cases; frozen before load.")
    load: Load = Field(default_factory=Load, description="Concurrency and resource limits.")
    plan_id: str | None = Field(default=None, description="Reuse a persisted evaluation plan UUID.")


class Selection(Model):
    """A catalog scorer proposed by the planner."""

    scorer: Literal["relevance", "correctness", "safety", "groundedness"]
    reason: str = Field(min_length=1, max_length=2000)


class PlannerOutput(Model):
    """Constrained planner output, validated independently of the model."""

    selections: list[Selection] = Field(max_length=4)
    registered_selections: list[str] = Field(default_factory=list, max_length=10)


class RegisteredScorer(Model):
    """Trusted operator-owned MLflow scorer frozen to an exact registry version."""

    alias: str = Field(
        pattern=r"^[a-zA-Z0-9_-]{1,64}$", description="Operator-allowlisted public scorer alias."
    )
    name: str = Field(min_length=1, max_length=128, description="Registered MLflow scorer name.")
    experiment_id: str = Field(
        min_length=1, max_length=128, description="Operator-authorized scorer registry experiment."
    )
    version: int = Field(
        ge=1, description="Exact registered version, never a mutable latest alias."
    )
    required_fields: list[Literal["inputs", "outputs", "expectations", "trace"]] = Field(
        default_factory=lambda: ["inputs", "outputs"],
        description="Evidence required for eligibility, including actual correlated Trace objects.",
    )
    description: str = Field(
        default="", max_length=2000, description="Operator-reviewed scorer purpose."
    )
    definition_hash: str = Field(description="SHA-256 of the frozen serialized scorer definition.")


class TraceSource(Model):
    """Operator-owned trace-store scope; callers cannot supply a tracking destination."""

    tracking_uri: str = Field(description="Frozen operator-selected MLflow destination.")
    experiment_ids: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Experiments authorized for correlated trace reads.",
    )
    max_traces: int = Field(
        default=100, ge=1, le=200, description="Maximum distinct traces fetched per run."
    )
    max_spans: int = Field(
        default=250, ge=1, le=1000, description="Maximum spans accepted in one complete trace."
    )


class Recommendation(Model):
    """A proposed scorer with deterministic evidence readiness and coverage."""

    scorer: str
    reason: str
    status: Literal["ready", "needs_data"]
    required_fields: list[str] = Field(description="Evidence required by this scorer.")
    eligible_samples: int = Field(description="Cases with the required pre-load evidence.")
    total_samples: int = Field(description="Total submitted workload cases.")


class Plan(Model):
    """Persisted pre-load evaluation policy; hashes bind data and installed rubric sources."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    version: str = "3"
    source: Literal["explicit", "llm"]
    planner_model: str | None = None
    judge_model: str | None = None
    judge_profile: str | None = None
    judge_host: str | None = None
    judge_max_completion_tokens: int = 2048
    judge_max_retries: int = 2
    judge_timeout_seconds: int = 60
    rubric_version: str = "mlflow-3.16-rubrics-v1"
    rubric_hash: str = Field(description="SHA-256 of the installed MLflow prompt sources.")
    dataset_hash: str = Field(description="SHA-256 of canonical workload samples and references.")
    evaluation_hash: str = Field(
        description="SHA-256 of all evaluation inputs, including sampling settings."
    )
    max_scored_requests: int = Field(description="Frozen maximum assessments per scorer.")
    sampling_seed: int = Field(description="Frozen deterministic sampling seed.")
    sampling_policy: str = "case-time-stratified-v1"
    time_bins: int = 4
    description: str = Field(description="Original objective and quality criteria.")
    registered_scorers: list[RegisteredScorer] = Field(
        default_factory=list, description="Frozen trusted scorer versions and definition hashes."
    )
    tracking_uri: str | None = Field(default=None, description="Operator-selected MLflow store.")
    trace_source: TraceSource | None = Field(default=None, description="Frozen opt-in trace scope.")
    recommendations: list[Recommendation] = Field(
        description="Catalog selections and evidence requirements."
    )
    notes: list[str] = Field(default_factory=list)


class Accepted(Model):
    """Resource identifier and relative polling URL."""

    id: str = Field(description="Resource UUID.")
    status: str = Field(description="Lifecycle status, not a quality pass/fail verdict.")
    url: str = Field(description="Relative URL to poll this resource.")


class ErrorDetail(Model):
    """Stable error code, safe message, and server request correlation identifier."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Safe human-readable explanation.")
    request_id: str = Field(description="Correlates this error with X-Request-ID.")


class ErrorResponse(Model):
    """Consistent error envelope used by API and validation failures."""

    error: ErrorDetail = Field(description="Error details without echoed request data.")


class PreflightError(Model):
    """Safe inference-check failure; never includes provider bodies or exception text."""

    code: Literal[
        "authentication_failed",
        "target_http_error",
        "target_timeout",
        "target_connection_error",
        "invalid_stream",
        "invalid_response",
        "worker_failed",
    ] = Field(description="Machine-readable inference-check failure category.")
    message: str = Field(description="Safe explanation and corrective guidance.")


class PreflightResult(Model):
    """Extra first-case invocation, excluded from measured metrics, profiles, and quality."""

    status: Literal[
        "not_run", "pending", "running", "passed", "failed", "cancelled", "interrupted"
    ] = Field(
        default="not_run", description="not_run also identifies historical runs without a check."
    )
    request_id: str | None = Field(
        default=None, description="Probe attempt correlation ID, when an attempt was recorded."
    )
    case_id: int = Field(default=0, description="The probe always uses workload case zero.")
    latency_ms: float | None = Field(
        default=None, ge=0, description="Probe client latency, not a benchmark measurement."
    )
    http_status: int | None = Field(
        default=None, ge=100, le=599, description="Target HTTP status, when received."
    )
    error: PreflightError | None = Field(default=None, description="Safe failure details.")


class EvaluationError(Model):
    """Content-free evaluation failure with corrective guidance, never provider text."""

    code: str = Field(description="Machine-readable evaluation failure category.")
    message: str = Field(description="Safe explanation, not an exception or provider body.")
    guidance: str = Field(description="Action the operator can take before another run.")
    scorer: str | None = Field(default=None, description="Frozen criterion that failed.")
    http_status: int | None = Field(default=None, ge=100, le=599)


class EvaluationPreflight(Model):
    """One readiness assessment per criterion, outside measured load and quality results."""

    status: Literal[
        "not_run", "pending", "running", "skipped", "passed", "failed", "cancelled", "interrupted"
    ] = "not_run"
    checked_scorers: list[str] = Field(default_factory=list)
    error: EvaluationError | None = None


class LoadError(Model):
    """Safe worker failure without process output, paths, credentials, or prompts."""

    code: Literal["worker_start_failed", "worker_failed", "worker_timeout"]
    message: str
    guidance: str


class RunResponse(Model):
    """Run snapshot; inspect preflight and independent phase outcomes separately."""

    id: str = Field(description="Resource UUID.")
    status: RunStatus = Field(description="Lifecycle status, not a quality pass/fail verdict.")
    load_status: LoadStatus = Field(
        description="Load phase outcome; skipped when preflight does not pass."
    )
    evaluation_status: EvaluationStatus = Field(
        description="Evaluation phase outcome; completed only when selected assessments succeed."
    )
    profiling_status: Literal["pending", "completed", "failed", "skipped"] = Field(
        default="pending",
        description="Collection phase outcome; inspect trace coverage separately.",
    )
    preflight: PreflightResult = Field(
        default_factory=PreflightResult,
        description="Mandatory first-case inference check before measured load; historical runs use not_run.",
    )
    evaluation_preflight: EvaluationPreflight = Field(
        default_factory=EvaluationPreflight,
        description="Selected judges must assess the inference probe before load; historical runs use not_run.",
    )
    load_error: LoadError | None = Field(
        default=None, description="Safe load-worker failure details."
    )
    config: RunRequest
    plan: Plan
    trace_coverage: str = Field(
        description="Scope of observability evidence available to this run."
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Descriptive client performance metrics and measurement coverage.",
    )
    evaluation: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-scorer MLflow run IDs, scores, safe execution errors, sampling coverage, and bounded request-correlated assessments. Judge rationales can contain protected evaluation content.",
    )
    error_type: str | None = None


class SpanProfile(Model):
    """Content-free normalized span; times are relative to the agent trace origin."""

    span_id: str = Field(description="Unique span identifier within the correlated trace.")
    parent_id: str | None = Field(description="Parent span identifier; null for the root.")
    name: str = Field(description="Truncated operation name, without span inputs or outputs.")
    category: Literal["model", "tool", "retrieval", "memory", "orchestration"] = Field(
        description="Normalized operation category; simultaneous leaves use a separate wall bucket."
    )
    start_ms: float = Field(ge=0, description="Start offset in milliseconds from the agent root.")
    duration_ms: float = Field(ge=0, description="Inclusive span duration; overlaps are possible.")
    self_ms: float = Field(ge=0, description="Duration minus the union of direct-child intervals.")
    depth: int = Field(ge=0, description="Validated tree depth, with the root at zero.")
    status: str = Field(
        description="MLflow span status; independent of the client request outcome."
    )


class RequestProfile(Model):
    """A correlated request trace or an explicit observability gap."""

    request_id: str = Field(description="Benchmark attempt identifier used for trace correlation.")
    case_id: int = Field(description="Zero-based workload case index.")
    success: bool = Field(description="Client-measured request success, not a quality verdict.")
    latency_ms: float | None = Field(description="Client latency in milliseconds when measured.")
    trace_id: str | None = Field(
        default=None, description="Target-provided MLflow trace identifier when available."
    )
    status: Literal[
        "available",
        "disabled",
        "missing",
        "scope_mismatch",
        "invalid",
        "budget",
        "collection_failed",
    ] = Field(description="Observed trace availability or an explicit evidence gap.")
    agent_duration_ms: float | None = Field(
        default=None, description="Complete agent-root duration in milliseconds, when validated."
    )
    client_minus_agent_ms: float | None = Field(
        default=None, description="Nonnegative duration difference, not proven network time."
    )
    occupancy_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Non-additive span trees reduced to exclusive wall-clock buckets; concurrent leaves use parallel.",
    )
    spans: list[SpanProfile] = Field(
        default_factory=list, description="Bounded content-free waterfall for an available trace."
    )


class ProfilingSummary(Model):
    """Trace coverage and descriptive span hotspots, never a causal critical-path claim."""

    total_requests: int = Field(description="Total captured attempts, including client failures.")
    traced_requests: int = Field(description="Attempts with validated correlated internal spans.")
    coverage: float = Field(
        ge=0, le=1, description="Validated trace count divided by total attempts."
    )
    gaps: dict[str, int] = Field(default_factory=dict, description="Counts by evidence-gap reason.")
    hotspots: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Inclusive per-operation timing summaries; overlaps remain.",
    )
    notes: list[str] = Field(
        default_factory=list, description="Attribution and measurement caveats."
    )


class MLflowExperimentLink(Model):
    """Credential-free browser destination for a recorded MLflow experiment."""

    experiment_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    url: str = Field(
        max_length=4096,
        pattern=r"^https?://",
        description="Operator-owned UI destination, never containing API credentials.",
    )
    scopes: list[Literal["traces", "evaluation"]] = Field(min_length=1, max_length=2)


class RunReport(Model):
    """One bounded report page joining performance, profiling, and quality evidence."""

    run: RunResponse = Field(
        description="Run configuration, independent phases, and client metrics."
    )
    profiling: ProfilingSummary = Field(description="Coverage and hotspots across the full run.")
    requests: list[RequestProfile] = Field(
        description="Request-profile page in attempt-start order."
    )
    offset: int = Field(description="Zero-based offset into request profiles.")
    limit: int = Field(description="Maximum returned profiles, at most 100.")
    total: int = Field(description="Total request profiles, including explicit evidence gaps.")
    mlflow_experiments: list[MLflowExperimentLink] = Field(
        default_factory=list,
        max_length=20,
        description="Available trace/evaluation experiment UI links; historical or unconfigured destinations are omitted.",
    )


class RequestPage(Model):
    """Bounded page of captured request records, including failures."""

    items: list[dict[str, Any]] = Field(
        description="Captured client records in attempt-start order."
    )
    offset: int = Field(description="Zero-based offset into request records.")
    limit: int = Field(description="Maximum returned records, at most 100.")
    total: int = Field(description="Known request records, including incomplete attempts.")


class RunSummary(Model):
    """Compact history entry without prompts, answers, or reference data."""

    id: str = Field(description="Run UUID.")
    status: RunStatus = Field(description="Overall lifecycle status.")
    load_status: LoadStatus = Field(description="Load phase outcome.")
    evaluation_status: EvaluationStatus = Field(description="Evaluation phase outcome.")
    url: str = Field(description="Relative URL for full metrics and evaluation results.")


class RunPage(Model):
    """Paginated local run history in UUID order."""

    items: list[RunSummary] = Field(description="Compact run summaries.")
    offset: int = Field(description="Zero-based history offset.")
    limit: int = Field(description="Maximum entries returned, at most 100.")
    total: int = Field(description="Number of runs matching the status filter.")
