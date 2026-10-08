"""Small v2 contracts translated into the existing evidence pipeline."""

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .models import (
    Evaluation,
    EvaluationPreflight,
    Load,
    LoadError,
    Model,
    PreflightResult,
    ProfilingSummary,
    RequestProfile,
    RunRequest,
    Sample,
    Target,
)


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
    status: str
    links: Links
    poll_after_seconds: float = Field(default=1, ge=0, le=60)


class PhaseStates(Model):
    """Independent planning, inference, load, profiling, and judging outcomes."""

    planning: str
    inference: str
    evaluation_readiness: str
    load: str
    profiling: str
    evaluation: str


class RunStatus(Model):
    """Lightweight polling response with no prompts, answers, or destinations."""

    id: UUID
    status: str
    name: str | None = None
    phases: PhaseStates
    links: Links
    poll_after_seconds: float = Field(default=1, ge=0, le=60)


class DecisionSummary(Model):
    """Completion does not imply a quality verdict or sustainable capacity."""

    performance: Literal["pending", "complete", "incomplete", "not_run"]
    quality: Literal["pending", "off", "available", "unavailable"]
    evidence_gaps: list[str] = Field(default_factory=list)
    sustainable_capacity_established: Literal[False] = False


class Timing(Model):
    """Successful client observations in milliseconds; absent values stay unknown."""

    count: int = Field(ge=0)
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None


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


class Result(Model):
    """Typed result envelope; protected assessment data retains native variants."""

    id: UUID
    status: str
    name: str | None = None
    phases: PhaseStates
    links: Links
    summary: DecisionSummary
    metrics: Performance | None = None
    preflight: PreflightResult
    evaluation_preflight: EvaluationPreflight
    evaluation: dict[str, Any] = Field(default_factory=dict)
    load_error: LoadError | None = None
    planning_error: dict[str, str] | None = None


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
