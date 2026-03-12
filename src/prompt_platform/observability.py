from __future__ import annotations

from pathlib import Path
from typing import Any

from prompt_platform.schemas import PromptRunContext
from prompt_platform.storage import FileArtifactStore


class TraceLogger:
    def __init__(self, artifact_store: FileArtifactStore) -> None:
        self.artifact_store = artifact_store

    def log_run(self, context: PromptRunContext, payload: dict[str, Any]) -> Path:
        return self.artifact_store.write_json(
            f"traces/{context.prompt_name}_v{context.version}_{context.trace_id or 'trace'}.json",
            {"context": context.model_dump(mode="json"), "payload": payload},
        )
