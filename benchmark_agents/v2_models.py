"""Small v2 contracts translated into the existing evidence pipeline."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, field_serializer, model_validator

from .models import (
    Evaluation,
    EvaluationError,
    EvaluationPreflight,
    EvaluationStatus,
    Load,
    LoadError,
    LoadStatus,
    Model,
    PreflightResult,
    ProfilingPreflight,
    ProfilingSummary,
    Recommendation,
    RequestProfile,
    RunRequest,
    Sample,
    Target,
)

LifecycleStatus = Literal[
    "queued",
    "planning",
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
EvidenceGap = Literal[
    "incomplete_measurements",
    "evaluation_unavailable",
    "planning_failed",
    "internal_trace_coverage",
    "profiling_failed",
    "generator_health_unavailable",
    "generator_degraded",
]


class TargetReference(Model):
    """Only an operator-registered target name crosses the public v2 boundary."""

    connection_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class Case(Model):
    """One bounded workload case and caller-owned authoritative evidence."""

    input: dict[str, Any] = Field(
        description="For fixed message protocols, exactly one nonempty query or messages array; extra top-level inference fields are rejected. For http-json, the raw nonempty POST body. Evaluation evidence belongs in reference."
    )
    reference: dict[str, Any] = Field(default_factory=dict)


class EvaluationPolicy(Model):
    """Planning and judging are opt-in; off bypasses both provider paths."""

    mode: Literal["off", "automatic", "explicit"] = "off"
    description: str = Field(
        default="Benchmark captured agent answers", min_length=1, max_length=10000
    )
    scorers: list[str] = Field(default_factory=list, max_length=10)
    max_scored_requests: int = Field(default=20, ge=1, le=1000)
    sampling_seed: int = Field(default=42, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def validate_mode(self) -> "EvaluationPolicy":
        """Require explicit criteria and disallow ignored scorer selections."""
        if self.mode == "explicit" and not self.scorers:
            raise ValueError("Explicit evaluation requires scorer IDs")
        if self.mode != "explicit" and self.scorers:
            raise ValueError("Scorer IDs require explicit evaluation")
        if len(set(self.scorers)) != len(self.scorers):
            raise ValueError("Scorer IDs must be unique")
        if any(not item or len(item) > 75 for item in self.scorers):
            raise ValueError("Scorer IDs exceed the supported bounds")
        return self


class RunCreate(Model):
    """Golden path: a registered target, cases, one load level, optional judging."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    target: TargetReference
    cases: list[Case] = Field(min_length=1, max_length=1000)
    load: Load = Field(default_factory=Load)
    evaluation: EvaluationPolicy = Field(default_factory=EvaluationPolicy)

    def translate(self, target: Target, registered_aliases: set[str]) -> RunRequest:
        """Build a detached v1 request without resolving credentials or invoking models.

        Args:
            target: Operator-resolved protocol and exact destination.
            registered_aliases: Approved scorer aliases, never executable caller code.

        Returns:
            Bounded workload for the one existing coordinator and Locust engine.

        Raises:
            ValueError: A requested criterion is not in the approved catalog.
        """
        catalog = {"relevance", "correctness", "safety", "groundedness"}
        catalog_ids = []
        aliases = []
        for scorer in self.evaluation.scorers:
            if scorer in catalog:
                catalog_ids.append(scorer)
            else:
                alias = scorer.removeprefix("registered:")
                if alias not in registered_aliases:
                    raise ValueError("Unknown registered scorer")
                aliases.append(alias)
        return RunRequest(
            target=target,
            load=self.load.model_copy(deep=True),
            evaluation=Evaluation(
                description=self.evaluation.description,
                samples=[
                    Sample(inputs=case.input, expectations=case.reference) for case in self.cases
                ],
                scorers=None if self.evaluation.mode == "automatic" else catalog_ids,
                registered_scorers=None if self.evaluation.mode == "automatic" else aliases,
                max_scored_requests=self.evaluation.max_scored_requests,
                sampling_seed=self.evaluation.sampling_seed,
            ),
        )


class Links(Model):
    """Same-origin resource paths; credentials never enter links."""

    status: str
    result: str
    report: str
    cancel: str

    @classmethod
    def for_run(cls, run_id: str) -> "Links":
        """Build paths from a validated resource identifier."""
        root = f"/v2/runs/{UUID(run_id)}"
        return cls(
            status=root, result=root + "/result", report=root + "/report", cancel=root + "/cancel"
        )


class Acknowledgment(Model):
    """Admission receipt; completion and quality are separate outcomes."""

    id: UUID
    status: LifecycleStatus | Literal["cancellation_requested"]
    links: Links
    poll_after_seconds: float = Field(default=1, ge=0, le=60)


class PhaseStates(Model):
    """Independent planning, inference, load, profiling, and judging outcomes."""

    planning: Literal["pending", "running", "completed", "failed", "cancelled", "interrupted"]
    inference: Literal[
        "not_run", "pending", "running", "passed", "failed", "cancelled", "interrupted"
    ]
    evaluation_readiness: Literal[
        "not_run", "pending", "running", "skipped", "passed", "failed", "cancelled", "interrupted"
    ]
    profiling_readiness: Literal[
        "not_run", "pending", "running", "skipped", "passed", "failed", "cancelled", "interrupted"
    ] = "not_run"
    load: LoadStatus
    profiling: Literal["pending", "completed", "failed", "skipped"]
    evaluation: EvaluationStatus


class RunStatus(Model):
    """Lightweight polling response with no prompts, answers, or destinations."""

    id: UUID
    status: LifecycleStatus
    name: str | None = None
    phases: PhaseStates
    links: Links
    poll_after_seconds: float = Field(default=1, ge=0, le=60)


class DecisionSummary(Model):
    """Completion does not imply a quality verdict or sustainable capacity."""

    performance: Literal["pending", "complete", "incomplete", "not_run"]
    quality: Literal["pending", "off", "available", "unavailable"]
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    sustainable_capacity_established: Literal[False] = False


class EvidenceCapability(Model):
    """Feature selection and observed evidence, not proof of quality or capacity.

    Configuration comes only from the frozen run policy and stays unknown for
    historical payloads that do not record it. Counts exclude inference probes
    and judge-readiness assessments. Load counts cover all recorded measured
    attempts, including failures, not successful latency or completeness. Profile
    counts cover validated traces; assessment counts cover scorer/attempt pairs.
    """

    configured: bool | None = Field(
        default=None,
        description="Frozen feature selection; null means historical configuration is unknown, not false.",
    )
    state: Literal["pending", "observed", "unavailable", "off"] = "pending"
    observed_count: int = Field(default=0, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    coverage: float | None = Field(default=None, ge=0, le=1)
    guidance: str = Field(default="", max_length=500)


class EvidenceCapabilities(Model):
    """Independent client, answer, internal-span and trace-aware evidence.

    Default entries preserve old response compatibility without asserting that
    configuration, authentication, model execution or evidence was verified.
    """

    load_measurements: EvidenceCapability = Field(default_factory=EvidenceCapability)
    answer_evaluation: EvidenceCapability = Field(default_factory=EvidenceCapability)
    internal_profiling: EvidenceCapability = Field(default_factory=EvidenceCapability)
    trace_aware_evaluation: EvidenceCapability = Field(default_factory=EvidenceCapability)


class Timing(Model):
    """Successful client observations in milliseconds; absent values stay unknown."""

    count: int = Field(ge=0)
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None


class GeneratorTiming(Model):
    """Constant-space observed durations in milliseconds, not request attribution."""

    count: int = Field(ge=0)
    mean_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class HubLag(GeneratorTiming):
    """Wake-up lateness on the generator hub; includes all hub scheduling work."""

    interval_ms: float = Field(gt=0, allow_inf_nan=False)


class JournalHealth(Model):
    """Durable writer observations; overlapping waits must not be summed.

    Event counts cover fsync-acknowledged events only. Pending events include the
    bounded FIFO and one native write. A drained writer is not proof of disk-loss
    tolerance, an unsaturated generator, or accurate server-only latency.
    """

    queue_capacity: int = Field(ge=1, le=16)
    peak_pending: int = Field(ge=0, le=17)
    backpressure_events: int = Field(ge=0)
    writer_failures: int = Field(ge=0)
    started_events: int = Field(ge=0)
    completed_events: int = Field(ge=0)
    drained: bool
    enqueue_wait_ms: GeneratorTiming
    durable_wait_ms: GeneratorTiming
    write_and_fsync_ms: GeneratorTiming


class GeneratorHealth(Model):
    """Content-free observations, never an accuracy certification or capacity gate.

    Unknown is normal even when observations are available: no calibrated healthy
    threshold exists. Degraded denotes a known journal failure or uncertain drain.
    CPU, memory, transport and server-only timing remain outside these observations.
    """

    status: Literal["unknown", "degraded"]
    observation_window: Literal["dispatch_and_drain"]
    hub_lag: HubLag
    journal: JournalHealth
    limitations: list[Annotated[str, Field(max_length=500)]] = Field(
        default_factory=list, max_length=10
    )


class Performance(Model):
    """Typed client metrics from one closed-loop concurrency level."""

    requests: int = Field(ge=0)
    successful_requests: int = Field(ge=0)
    error_rate: float | None = None
    successful_tps: float
    completed_tps: float
    elapsed_seconds_including_drain: float
    dispatch_seconds: float
    token_usage_coverage: float
    reported_output_tokens_per_second: float | None = None
    timing_successful_only: dict[str, Timing]
    errors: dict[str, int] = Field(default_factory=dict)
    measurement_complete: bool = False
    configured_concurrency: int | None = None
    observed_peak_in_flight: int | None = None
    generator_health: GeneratorHealth | None = Field(
        default=None,
        description="Generator observations, not verified accuracy. Null means historical or missing telemetry; never assume a healthy runner.",
    )


class SamplingStratum(Model):
    """Selected captures in one zero-based case/time bucket, not a population weight."""

    case_id: int = Field(ge=0)
    time_bin: int = Field(ge=0)
    selected: int = Field(ge=0)


class SamplingCoverage(Model):
    """Evidence-qualified selection coverage with the frozen case/time policy."""

    policy: str
    seed: int = Field(ge=0)
    time_bins: int = Field(ge=1)
    observed_dispatch_window_ms: float = Field(ge=0)
    eligible: int = Field(ge=0)
    selected: int = Field(ge=0)
    fraction_of_eligible: float = Field(ge=0, le=1)
    eligible_strata: int = Field(ge=0)
    selected_strata: int = Field(ge=0)
    strata: list[SamplingStratum] = Field(default_factory=list)


class RequestCoverage(Model):
    """All measured attempts; only successful evidence-qualified outputs are judged."""

    total: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)


class AssessmentOutcome(Model):
    """Protected native assessment; a false verdict is not an execution failure."""

    request_id: str
    case_id: int | None = Field(default=None, ge=0)
    status: Literal["passed", "failed", "scored", "error", "unavailable"]
    value: bool | int | float | str | None = None
    rationale: str | None = Field(default=None, max_length=2000)
    rationale_truncated: bool = False
    error: EvaluationError | None = None


class ScorerOutcome(Model):
    """One judge's execution, coverage and optional boolean pass rate, independently."""

    scorer: str
    status: Literal[
        "completed",
        "partial",
        "failed",
        "configuration_changed",
        "needs_configuration",
        "no_eligible_outputs",
    ]
    eligible: int | None = Field(default=None, ge=0)
    attempted: int | None = Field(default=None, ge=0)
    scored: int | None = Field(default=None, ge=0)
    judge_errors: int | None = Field(default=None, ge=0)
    coverage: SamplingCoverage | None = None
    request_ids: list[str] = Field(default_factory=list)
    assessments: list[AssessmentOutcome] = Field(default_factory=list)
    mlflow_run_id: str | None = None
    mlflow_experiment_id: str | None = None
    metrics: dict[str, float | None] = Field(default_factory=dict)
    pass_rate: float | None = Field(default=None, ge=0, le=1)
    source: Literal["registered-mlflow", "catalog"] | None = None
    version: str | int | None = None
    error: EvaluationError | None = None


class EvaluationOutcome(Model):
    """Typed captured-answer evidence; absent fields remain unknown for legacy runs.

    Model execution completion is not a quality pass. Registered scores need an
    explicit caller threshold; only boolean values have an intrinsic pass rate.
    Rationales are protected content and can quote prompts or references.
    """

    status: EvaluationStatus | None = None
    results: list[ScorerOutcome] = Field(default_factory=list)
    needs_data: list[Recommendation] = Field(default_factory=list)
    request_coverage: RequestCoverage | None = None
    judge_model: str | None = None
    transport: Literal["databricks-sdk"] | None = None
    required: list[str] = Field(default_factory=list)
    error: EvaluationError | None = None
    error_type: str | None = None


class Result(Model):
    """Typed result envelope; protected assessment data retains native variants."""

    id: UUID
    status: LifecycleStatus
    name: str | None = None
    phases: PhaseStates
    links: Links
    summary: DecisionSummary
    evidence: EvidenceCapabilities = Field(default_factory=EvidenceCapabilities)
    metrics: Performance | None = None
    preflight: PreflightResult
    evaluation_preflight: EvaluationPreflight
    profiling_preflight: ProfilingPreflight = Field(default_factory=ProfilingPreflight)
    evaluation: EvaluationOutcome = Field(default_factory=EvaluationOutcome)
    load_error: LoadError | None = None
    planning_error: dict[str, str] | None = None

    @field_serializer("evaluation")
    def serialize_evaluation(self, outcome: EvaluationOutcome):
        """Preserve partial wire payloads and the declared typed OpenAPI schema.

        Args:
            outcome: Native typed evaluation, including only observed fields.

        Returns:
            JSON-compatible observed fields. A return annotation is deliberately
            omitted because Pydantic uses it to replace the field's output schema;
            the public contract must remain EvaluationOutcome, not an untyped dict.
        """
        return outcome.model_dump(exclude_unset=True)


class Report(Model):
    """Protected paginated report without operator credentials or target configuration."""

    run: Result
    profiling: ProfilingSummary
    requests: list[RequestProfile]
    offset: int
    limit: int
    total: int


class ValidationIssue(Model):
    """Bounded schema guidance with public field names, never values or arbitrary keys."""

    location: list[str | int] = Field(max_length=12)
    code: str = Field(max_length=64)
    message: str = Field(max_length=200)


class V2ErrorDetail(Model):
    """Fixed safe error guidance; provider text and submitted values are excluded."""

    code: str
    message: str
    request_id: str
    phase: str
    retryable: bool
    guidance: str
    errors: list[ValidationIssue] | None = Field(
        default=None,
        max_length=20,
        description="At most 20 sanitized validation issues; arbitrary input keys are replaced by <extra>.",
    )


class V2ErrorResponse(Model):
    """Versioned common error envelope."""

    error: V2ErrorDetail
