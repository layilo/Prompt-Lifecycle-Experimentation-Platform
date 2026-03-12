from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from prompt_platform.registry import PromptRegistry
from prompt_platform.schemas import PromptRunContext, PromptVersion
from prompt_platform.utils import load_json


class PromptResolver:
    def __init__(self, registry: PromptRegistry, snapshot_path: Optional[Path] = None) -> None:
        self.registry = registry
        self.snapshot_path = snapshot_path
        self._cache: dict[str, PromptVersion] = {}

    def fetch(self, reference: str) -> PromptVersion:
        if reference in self._cache:
            return self._cache[reference]
        try:
            prompt = self.registry.resolve(reference)
        except KeyError:
            if not self.snapshot_path or not self.snapshot_path.exists():
                raise
            prompt = self._fetch_from_snapshot(reference)
        self._cache[reference] = prompt
        return prompt

    def _fetch_from_snapshot(self, reference: str) -> PromptVersion:
        payload = load_json(self.snapshot_path)
        name, marker = reference.split("@", 1) if "@" in reference else (reference, None)
        records = payload[name]["versions"]
        aliases = {item["alias"]: item["version"] for item in payload[name]["aliases"]}
        if marker:
            version = aliases[marker]
        else:
            version = records[-1]["version"]
        for record in records:
            if record["version"] == version:
                return PromptVersion.model_validate(record)
        raise KeyError(reference)

    @staticmethod
    def render(prompt: PromptVersion, variables: dict[str, Any]) -> str:
        text = prompt.definition.template
        for key, value in variables.items():
            text = text.replace(f"{{{{ {key} }}}}", str(value))
        return text

    @staticmethod
    def build_run_context(prompt: PromptVersion, environment: str, backend: str) -> PromptRunContext:
        model = prompt.definition.default_model.get("model", "unknown")
        return PromptRunContext(
            prompt_name=prompt.name,
            version=prompt.version,
            environment=environment,
            backend=backend,
            model=model,
            generation_params=prompt.definition.default_generation_params,
            release_sha=os.getenv("GIT_SHA", ""),
        )
