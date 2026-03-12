from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PromptTemplateVariable(BaseModel):
    name: str
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


class PromptMetadata(BaseModel):
    tags: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    created_by: str = "unknown"
    created_at: datetime = Field(default_factory=utc_now)
    commit_message: str = ""
    notes: str = ""
    archived: bool = False
    deprecated: bool = False
    hypotheses: list[str] = Field(default_factory=list)


class PromptDefinition(BaseModel):
    name: str
    task_type: str
    description: str = ""
    template: str
    variables: list[PromptTemplateVariable] = Field(default_factory=list)
    default_model: dict[str, Any] = Field(default_factory=dict)
    default_generation_params: dict[str, Any] = Field(default_factory=dict)
    metadata: PromptMetadata = Field(default_factory=PromptMetadata)


class PromptVersion(BaseModel):
    name: str
    version: int
    definition: PromptDefinition
    immutable_id: str
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = "unknown"
    change_message: str = ""
    parent_version: Optional[int] = None
    linked_experiments: list[str] = Field(default_factory=list)
    linked_evaluations: list[str] = Field(default_factory=list)
    linked_runs: list[str] = Field(default_factory=list)


class PromptAlias(BaseModel):
    name: str
    alias: str
    version: int
    updated_at: datetime = Field(default_factory=utc_now)
    updated_by: str = "unknown"
    reason: str = ""


class PromptChangeRecord(BaseModel):
    name: str
    version: int
    changed_by: str
    changed_at: datetime = Field(default_factory=utc_now)
    message: str
    diff_summary: dict[str, Any] = Field(default_factory=dict)


class PromptVariant(BaseModel):
    id: str
    prompt_name: str
    version: int
    backend: str = "mock"
    parameters: dict[str, Any] = Field(default_factory=dict)


class PromptExperiment(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt_name: str
    variants: list[PromptVariant]
    dataset_path: str
    repeats: int = 1
    metrics: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationCase(BaseModel):
    id: str
    task_type: str
    inputs: dict[str, Any]
    expected: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    name: str
    path: str
    cases: list[EvaluationCase]
    version: str = "1"


class EvaluationCaseResult(BaseModel):
    case_id: str
    output: Any
    expected: Any
    score: float
    passed: bool
    metrics: dict[str, float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    structured_valid: bool = True


class EvaluationResult(BaseModel):
    run_id: str
    prompt_name: str
    version: int
    dataset_name: str
    backend: str
    mode: Literal["mock", "real"] = "mock"
    aggregate_metrics: dict[str, float]
    case_results: list[EvaluationCaseResult]
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegressionCheck(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    passed: bool
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metric_deltas: dict[str, float] = Field(default_factory=dict)


class ABTestConfig(BaseModel):
    name: str
    prompt_name: str
    variants: dict[str, dict[str, Any]]
    sticky_by: str = "user_id"
    simulated_users: int = 100
    success_metric: str = "thumbs_up_rate"
    start_at: Any
    end_at: Any


class ABTestAssignment(BaseModel):
    experiment_name: str
    subject_id: str
    variant_id: str
    version: int
    exposed_at: datetime = Field(default_factory=utc_now)


class OnlineMetricSnapshot(BaseModel):
    variant_id: str
    exposures: int
    success_rate: float
    retry_rate: float
    latency_ms: float
    token_cost: float
    structured_validity: float


class PromotionDecision(BaseModel):
    prompt_name: str
    baseline_version: int
    candidate_version: int
    recommendation: Literal["promote", "hold", "rollback"]
    rationale: list[str]
    evidence: dict[str, Any] = Field(default_factory=dict)
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class DeploymentRecord(BaseModel):
    prompt_name: str
    alias: str
    version: int
    deployed_at: datetime = Field(default_factory=utc_now)
    deployed_by: str = "unknown"
    environment: str = "dev"
    approval: str = ""


class PromptLineageRecord(BaseModel):
    prompt_name: str
    version: int
    parents: list[int] = Field(default_factory=list)
    experiments: list[str] = Field(default_factory=list)
    evaluations: list[str] = Field(default_factory=list)
    deployments: list[str] = Field(default_factory=list)


class PromptRunContext(BaseModel):
    prompt_name: str
    version: int
    environment: str
    backend: str
    model: str
    generation_params: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""
    session_id: str = ""
    release_sha: str = ""
    dataset_version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
