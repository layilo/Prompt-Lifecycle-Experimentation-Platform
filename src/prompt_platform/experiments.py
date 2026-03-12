from __future__ import annotations

from pathlib import Path
from typing import Any

from prompt_platform.evaluation import EvaluationEngine
from prompt_platform.model_backends import build_model_client
from prompt_platform.schemas import PromptExperiment, PromptVariant
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore
from prompt_platform.utils import load_yaml


class ExperimentRunner:
    def __init__(
        self,
        evaluation_engine: EvaluationEngine,
        metadata_store: SQLiteMetadataStore,
        artifact_store: FileArtifactStore,
        backend_configs: dict[str, dict[str, Any]],
        mode: str,
    ) -> None:
        self.evaluation_engine = evaluation_engine
        self.metadata_store = metadata_store
        self.artifact_store = artifact_store
        self.backend_configs = backend_configs
        self.mode = mode

    def load_experiment(self, path: Path) -> PromptExperiment:
        payload = load_yaml(path)
        variants = [
            PromptVariant(
                id=item["id"],
                prompt_name=payload["prompt_name"],
                version=item["version"],
                backend=payload.get("backend", "mock"),
            )
            for item in payload["variants"]
        ]
        return PromptExperiment(
            id=path.stem,
            name=payload["name"],
            description=payload.get("description", ""),
            prompt_name=payload["prompt_name"],
            variants=variants,
            dataset_path=payload["dataset"],
            repeats=payload.get("repeats", 1),
            metrics=payload.get("metrics", ["exact_match"]),
        )

    def run(self, path: Path) -> dict[str, Any]:
        experiment = self.load_experiment(path)
        leaderboard: list[dict[str, Any]] = []
        for variant in experiment.variants:
            client = build_model_client(variant.backend, self.backend_configs[variant.backend], model="mock-model")
            result = self.evaluation_engine.run(
                prompt_reference=f"{variant.prompt_name}:{variant.version}",
                dataset_path=Path(experiment.dataset_path),
                backend=variant.backend,
                model_client=client,
                mode=self.mode,
                metrics=["exact_match", "token_f1", "bleu", "rouge_l"],
            )
            self.metadata_store.write_evaluation_result(result)
            self.artifact_store.write_json(
                f"evaluations/{experiment.prompt_name}_{variant.id}.json",
                result.model_dump(mode="json"),
            )
            weighted_score = (
                0.5 * result.aggregate_metrics["accuracy"]
                + 0.2 * result.aggregate_metrics["pass_rate"]
                + 0.2 * result.aggregate_metrics["structured_validity"]
                - 0.1 * min(result.aggregate_metrics["latency_ms"] / 1000, 1.0)
            )
            leaderboard.append(
                {
                    "variant_id": variant.id,
                    "version": variant.version,
                    "run_id": result.run_id,
                    "weighted_score": round(weighted_score, 4),
                    **result.aggregate_metrics,
                }
            )
        leaderboard.sort(key=lambda item: item["weighted_score"], reverse=True)
        summary = {
            "experiment_id": experiment.id,
            "prompt_name": experiment.prompt_name,
            "leaderboard": leaderboard,
            "recommended_version": leaderboard[0]["version"],
        }
        self.artifact_store.write_json(f"experiments/{experiment.id}.json", summary)
        return summary

