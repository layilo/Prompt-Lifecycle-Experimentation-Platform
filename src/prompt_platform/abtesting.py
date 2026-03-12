from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from prompt_platform.schemas import ABTestAssignment, ABTestConfig, OnlineMetricSnapshot
from prompt_platform.utils import load_yaml


class ABTestSimulator:
    def load_config(self, path: Path) -> ABTestConfig:
        return ABTestConfig.model_validate(load_yaml(path))

    @staticmethod
    def assign_variant(subject_id: str, variants: dict[str, dict[str, Any]]) -> str:
        bucket = int(hashlib.sha256(subject_id.encode("utf-8")).hexdigest(), 16) % 100
        running = 0
        for variant_id, config in variants.items():
            running += int(config["weight"])
            if bucket < running:
                return variant_id
        return next(iter(variants))

    def simulate(self, path: Path) -> dict[str, Any]:
        config = self.load_config(path)
        assignments: list[ABTestAssignment] = []
        metrics: dict[str, list[float]] = {}
        for i in range(config.simulated_users):
            subject_id = f"user-{i}"
            variant_id = self.assign_variant(subject_id, config.variants)
            version = int(config.variants[variant_id]["version"])
            assignments.append(
                ABTestAssignment(
                    experiment_name=config.name,
                    subject_id=subject_id,
                    variant_id=variant_id,
                    version=version,
                )
            )
            success = 0.82 if variant_id == "treatment" else 0.71
            retry = 0.08 if variant_id == "treatment" else 0.12
            latency = 90.0 if variant_id == "treatment" else 85.0
            cost = 0.0025 if variant_id == "treatment" else 0.002
            structured = 0.99 if variant_id == "treatment" else 0.97
            metrics.setdefault(variant_id, []).append(success)
            metrics.setdefault(f"{variant_id}_retry", []).append(retry)
            metrics.setdefault(f"{variant_id}_latency", []).append(latency)
            metrics.setdefault(f"{variant_id}_cost", []).append(cost)
            metrics.setdefault(f"{variant_id}_structured", []).append(structured)
        snapshots: list[OnlineMetricSnapshot] = []
        for variant_id in config.variants:
            exposures = len([item for item in assignments if item.variant_id == variant_id])
            snapshots.append(
                OnlineMetricSnapshot(
                    variant_id=variant_id,
                    exposures=exposures,
                    success_rate=sum(metrics[variant_id]) / exposures,
                    retry_rate=sum(metrics[f"{variant_id}_retry"]) / exposures,
                    latency_ms=sum(metrics[f"{variant_id}_latency"]) / exposures,
                    token_cost=sum(metrics[f"{variant_id}_cost"]) / exposures,
                    structured_validity=sum(metrics[f"{variant_id}_structured"]) / exposures,
                )
            )
        winner = max(snapshots, key=lambda item: item.success_rate - item.retry_rate)
        return {
            "experiment_name": config.name,
            "assignments": [item.model_dump(mode="json") for item in assignments[:20]],
            "snapshots": [item.model_dump(mode="json") for item in snapshots],
            "winner": winner.variant_id,
            "recommended_version": config.variants[winner.variant_id]["version"],
        }

