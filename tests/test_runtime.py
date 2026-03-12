from pathlib import Path

from prompt_platform.registry import PromptRegistry
from prompt_platform.runtime import PromptResolver
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore


def test_prompt_rendering(tmp_path: Path) -> None:
    db = SQLiteMetadataStore(tmp_path / "metadata.db")
    artifacts = FileArtifactStore(tmp_path / "artifacts")
    registry = PromptRegistry(db, artifacts)
    root = Path.cwd()
    record = registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v1.yaml", "tester")
    resolver = PromptResolver(registry)
    rendered = resolver.render(record, {"customer_message": "Help with refund"})
    assert "Help with refund" in rendered

