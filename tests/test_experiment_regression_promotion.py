from pathlib import Path

from prompt_platform.evaluation import EvaluationEngine
from prompt_platform.experiments import ExperimentRunner
from prompt_platform.model_backends import MockModelClient
from prompt_platform.promotion import PromotionManager
from prompt_platform.regression import RegressionDetector
from prompt_platform.registry import PromptRegistry
from prompt_platform.runtime import PromptResolver
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore
from prompt_platform.utils import load_yaml


def test_experiment_regression_and_promotion_flow(tmp_path: Path) -> None:
    db = SQLiteMetadataStore(tmp_path / "metadata.db")
    artifacts = FileArtifactStore(tmp_path / "artifacts")
    registry = PromptRegistry(db, artifacts)
    root = Path.cwd()
    registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v1.yaml", "tester")
    registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v2.yaml", "tester")
    resolver = PromptResolver(registry)
    engine = EvaluationEngine(resolver)
    runner = ExperimentRunner(engine, db, artifacts, {"mock": {"provider": "mock", "seed": 1}}, "mock")
    experiment = runner.run(root / "configs" / "experiments" / "support_classifier_tournament.yaml")
    assert experiment["recommended_version"] in {1, 2}
    client = MockModelClient(seed=1)
    baseline = engine.run("support_classifier:1", root / "data" / "golden" / "support_classifier.jsonl", "mock", client)
    candidate = engine.run("support_classifier:2", root / "data" / "golden" / "support_classifier.jsonl", "mock", client)
    regression = RegressionDetector(load_yaml(root / "configs" / "thresholds" / "default.yaml")).check(baseline, candidate)
    manager = PromotionManager(registry, db, load_yaml(root / "configs" / "policies" / "promotion.yaml"))
    decision = manager.evaluate_candidate("support_classifier", baseline, candidate, regression, "staging", "platform-bot")
    assert decision.recommendation == "promote"

