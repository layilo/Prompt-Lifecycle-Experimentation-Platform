from __future__ import annotations

from pathlib import Path
from typing import Any

from prompt_platform.schemas import EvaluationResult, RegressionCheck
from prompt_platform.utils import load_json, load_yaml


class RegressionDetector:
    def __init__(self, thresholds: dict[str, Any]) -> None:
        self.thresholds = thresholds

    @classmethod
    def from_file(cls, path: Path) -> "RegressionDetector":
        return cls(load_yaml(path))

    def check(self, baseline: EvaluationResult, candidate: EvaluationResult) -> RegressionCheck:
        blocking_issues: list[str] = []
        warnings: list[str] = []
        deltas = {
            "accuracy": candidate.aggregate_metrics["accuracy"] - baseline.aggregate_metrics["accuracy"],
            "pass_rate": candidate.aggregate_metrics["pass_rate"] - baseline.aggregate_metrics["pass_rate"],
            "latency_ms": candidate.aggregate_metrics["latency_ms"] - baseline.aggregate_metrics["latency_ms"],
            "tokens_in": candidate.aggregate_metrics["tokens_in"] - baseline.aggregate_metrics["tokens_in"],
            "total_cost": candidate.aggregate_metrics["total_cost"] - baseline.aggregate_metrics["total_cost"],
            "structured_validity": candidate.aggregate_metrics["structured_validity"] - baseline.aggregate_metrics["structured_validity"],
        }
        if deltas["accuracy"] < -float(self.thresholds["accuracy_drop_max"]):
            blocking_issues.append("Accuracy regression exceeded threshold.")
        if candidate.aggregate_metrics["pass_rate"] < float(self.thresholds["pass_rate_min"]):
            blocking_issues.append("Pass rate below minimum threshold.")
        if baseline.aggregate_metrics["latency_ms"] > 0:
            ratio = candidate.aggregate_metrics["latency_ms"] / baseline.aggregate_metrics["latency_ms"]
            if ratio > float(self.thresholds["latency_increase_ratio_max"]):
                blocking_issues.append("Latency increase exceeded threshold.")
        if baseline.aggregate_metrics["tokens_in"] > 0:
            ratio = candidate.aggregate_metrics["tokens_in"] / baseline.aggregate_metrics["tokens_in"]
            if ratio > float(self.thresholds["token_increase_ratio_max"]):
                warnings.append("Token usage increased materially.")
        if baseline.aggregate_metrics["total_cost"] > 0:
            ratio = candidate.aggregate_metrics["total_cost"] / baseline.aggregate_metrics["total_cost"]
            if ratio > float(self.thresholds["cost_increase_ratio_max"]):
                warnings.append("Cost increased materially.")
        if deltas["structured_validity"] < -float(self.thresholds["structured_validity_drop_max"]):
            blocking_issues.append("Structured output validity regressed.")
        return RegressionCheck(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            passed=not blocking_issues,
            blocking_issues=blocking_issues,
            warnings=warnings,
            metric_deltas=deltas,
        )

    @staticmethod
    def load_result(path: Path) -> EvaluationResult:
        return EvaluationResult.model_validate(load_json(path))

