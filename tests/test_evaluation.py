from pathlib import Path

from prompt_platform.evaluation import EvaluationEngine
from prompt_platform.model_backends import MockModelClient
from prompt_platform.registry import PromptRegistry
from prompt_platform.runtime import PromptResolver
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore


def test_evaluation_engine_returns_expected_metrics(tmp_path: Path) -> None:
    db = SQLiteMetadataStore(tmp_path / "metadata.db")
    artifacts = FileArtifactStore(tmp_path / "artifacts")
    registry = PromptRegistry(db, artifacts)
    root = Path.cwd()
    registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v1.yaml", "tester")
    resolver = PromptResolver(registry)
    engine = EvaluationEngine(resolver)
    result = engine.run(
        "support_classifier:1",
        root / "data" / "golden" / "support_classifier.jsonl",
        backend="mock",
        model_client=MockModelClient(seed=1),
        metrics=["exact_match", "token_f1"],
    )
    assert result.aggregate_metrics["accuracy"] == 1.0
    assert result.aggregate_metrics["pass_rate"] == 1.0

