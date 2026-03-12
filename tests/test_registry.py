from pathlib import Path

from prompt_platform.registry import PromptRegistry
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore


def test_registry_versioning_and_alias_resolution(tmp_path: Path) -> None:
    db = SQLiteMetadataStore(tmp_path / "metadata.db")
    artifacts = FileArtifactStore(tmp_path / "artifacts")
    registry = PromptRegistry(db, artifacts)
    root = Path.cwd()
    v1 = registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v1.yaml", "tester")
    v2 = registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v2.yaml", "tester")
    assert v1.version == 1
    assert v2.version == 2
    assert registry.resolve("support_classifier@candidate").version == 2
    diff = registry.diff("support_classifier", 1, 2)
    assert "technical" in diff["template_diff"]

