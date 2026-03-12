from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from prompt_platform.utils import load_yaml


class EnvironmentConfig(BaseModel):
    name: str
    mode: str = "mock"
    storage_dir: str = "artifacts"
    db_path: str = "artifacts/metadata.db"
    default_backend: str = "mock"
    backend_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)


def load_environment_config(profile: str, base_dir: Optional[Path] = None) -> EnvironmentConfig:
    root = base_dir or Path.cwd()
    path = root / "configs" / "environments" / f"{profile}.yaml"
    return EnvironmentConfig.model_validate(load_yaml(path))
