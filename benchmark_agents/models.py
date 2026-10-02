"""Validated public API contracts."""

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Sample(Model):
    """One workload case and optional authoritative reference evidence."""

    inputs: dict[str, Any] = Field(
        description="A query string or a nonempty messages array.",
        examples=[{"query": "Can I refund?"}],
    )
    expectations: dict[str, Any] = Field(
        default_factory=dict,
        description="Authoritative expected_response or expected_facts; never invented by the planner.",
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
    """Hosted streaming endpoint and an optional server-owned connection reference."""

    url: HttpUrl = Field(
        description="Exact streaming URL authorized by server target policy.",
        examples=["http://127.0.0.1:9001/chat"],
    )
    adapter: Literal["openai-chat", "mlflow-agent-server"] = "openai-chat"
    framework: Literal["langgraph", "openai-agents"] | None = None
    model: str = "agent"
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
    reason: str


class PlannerOutput(Model):
    """Constrained planner output, validated independently of the model."""

    selections: list[Selection] = Field(max_length=4)


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
    version: str = "2"
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


class RunResponse(Model):
    """Run snapshot; inspect load_status and evaluation_status separately."""

    id: str = Field(description="Resource UUID.")
    status: str = Field(description="Lifecycle status, not a quality pass/fail verdict.")
    load_status: str = Field(
        description="Load phase: queued, running, completed, cancelled, interrupted, or failed."
    )
    evaluation_status: str = Field(
        description="Evaluation phase outcome; completed only when selected assessments succeed."
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
        description="Per-scorer MLflow run IDs, scores, errors, and sampling coverage.",
    )
    error_type: str | None = None


class RequestPage(Model):
    """Bounded page of captured request records, including failures."""

    items: list[dict[str, Any]] = Field(description="Captured client records in dispatch order.")
    offset: int = Field(description="Zero-based offset into request records.")
    limit: int = Field(description="Maximum returned records, at most 100.")
    total: int = Field(description="Known request records, including incomplete attempts.")


class RunSummary(Model):
    """Compact history entry without prompts, answers, or reference data."""

    id: str = Field(description="Run UUID.")
    status: str = Field(description="Overall lifecycle status.")
    load_status: str = Field(description="Load phase outcome.")
    evaluation_status: str = Field(description="Evaluation phase outcome.")
    url: str = Field(description="Relative URL for full metrics and evaluation results.")


class RunPage(Model):
    """Paginated local run history in UUID order."""

    items: list[RunSummary] = Field(description="Compact run summaries.")
    offset: int = Field(description="Zero-based history offset.")
    limit: int = Field(description="Maximum entries returned, at most 100.")
    total: int = Field(description="Number of runs matching the status filter.")
