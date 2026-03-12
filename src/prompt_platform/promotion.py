from __future__ import annotations

from typing import Any

from prompt_platform.registry import PromptRegistry
from prompt_platform.schemas import DeploymentRecord, EvaluationResult, PromotionDecision, RegressionCheck
from prompt_platform.storage import SQLiteMetadataStore


class PromotionManager:
    def __init__(self, registry: PromptRegistry, metadata_store: SQLiteMetadataStore, policy: dict[str, Any]) -> None:
        self.registry = registry
        self.metadata_store = metadata_store
        self.policy = policy

    def evaluate_candidate(
        self,
        prompt_name: str,
        baseline: EvaluationResult,
        candidate: EvaluationResult,
        regression: RegressionCheck,
        alias: str,
        requested_by: str,
        ab_summary: dict[str, Any] = None,
    ) -> PromotionDecision:
        rationale: list[str] = []
        recommendation = "hold"
        if regression.passed:
            rationale.append("Regression gates passed.")
            recommendation = "promote"
        else:
            rationale.extend(regression.blocking_issues)
        if ab_summary:
            if int(ab_summary["recommended_version"]) == candidate.version:
                rationale.append("Online A/B simulation favored candidate.")
            else:
                recommendation = "hold"
                rationale.append("A/B simulation did not favor candidate.")
        if alias == "production" and self.policy.get("require_manual_approval_for_prod", True):
            allowlist = set(self.policy.get("prod_allowlist", []))
            if requested_by not in allowlist:
                recommendation = "hold"
                rationale.append("Requester is not in production allowlist.")
        decision = PromotionDecision(
            prompt_name=prompt_name,
            baseline_version=baseline.version,
            candidate_version=candidate.version,
            recommendation=recommendation,
            rationale=rationale,
            evidence={
                "baseline_metrics": baseline.aggregate_metrics,
                "candidate_metrics": candidate.aggregate_metrics,
                "regression": regression.model_dump(mode="json"),
                "ab_summary": ab_summary or {},
            },
            approved_by=requested_by if recommendation == "promote" else None,
        )
        self.metadata_store.write_promotion_decision(decision)
        return decision

    def promote(self, prompt_name: str, alias: str, version: int, requested_by: str, environment: str) -> DeploymentRecord:
        self.registry.assign_alias(prompt_name, alias, version, requested_by, f"promotion to {environment}")
        record = DeploymentRecord(
            prompt_name=prompt_name,
            alias=alias,
            version=version,
            deployed_by=requested_by,
            environment=environment,
            approval="approved",
        )
        self.metadata_store.write_deployment_record(record)
        return record

    def rollback(self, prompt_name: str, alias: str, to_version: int, requested_by: str, environment: str) -> DeploymentRecord:
        self.registry.rollback_alias(prompt_name, alias, to_version, requested_by)
        record = DeploymentRecord(
            prompt_name=prompt_name,
            alias=alias,
            version=to_version,
            deployed_by=requested_by,
            environment=environment,
            approval="rollback",
        )
        self.metadata_store.write_deployment_record(record)
        return record
