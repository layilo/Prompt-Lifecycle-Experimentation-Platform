from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any

from prompt_platform.schemas import (
    PromptAlias,
    PromptChangeRecord,
    PromptDefinition,
    PromptMetadata,
    PromptVersion,
)
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore
from prompt_platform.utils import load_yaml, stable_hash


@dataclass
class RegistrySearchResult:
    name: str
    versions: list[int]
    aliases: dict[str, int]


class PromptRegistry:
    def __init__(self, metadata_store: SQLiteMetadataStore, artifact_store: FileArtifactStore) -> None:
        self.metadata_store = metadata_store
        self.artifact_store = artifact_store

    def _definition_from_file(self, path: Path) -> PromptDefinition:
        payload = load_yaml(path)
        metadata = PromptMetadata.model_validate(payload.pop("metadata", {}))
        return PromptDefinition.model_validate({**payload, "metadata": metadata.model_dump()})

    def create_or_version(
        self,
        path: Path,
        created_by: str = "unknown",
        parent_version: int = None,
    ) -> PromptVersion:
        definition = self._definition_from_file(path)
        existing = self.metadata_store.list_prompt_versions(definition.name)
        next_version = 1 if not existing else existing[-1].version + 1
        immutable_id = stable_hash({"name": definition.name, "version": next_version, "template": definition.template})
        record = PromptVersion(
            name=definition.name,
            version=next_version,
            definition=definition,
            immutable_id=immutable_id,
            created_by=created_by or definition.metadata.created_by,
            change_message=definition.metadata.commit_message,
            parent_version=parent_version if parent_version is not None else (existing[-1].version if existing else None),
        )
        self.metadata_store.upsert_prompt_version(record)
        self.artifact_store.write_json(
            f"registry/{definition.name}/versions/v{next_version}.json",
            record.model_dump(mode="json"),
        )
        diff_summary = {}
        if existing:
            diff_summary = self.diff(definition.name, existing[-1].version, next_version)
        self.metadata_store.write_change_record(
            PromptChangeRecord(
                name=definition.name,
                version=next_version,
                changed_by=record.created_by,
                message=record.change_message,
                diff_summary=diff_summary,
            )
        )
        for alias in definition.metadata.labels:
            self.assign_alias(definition.name, alias, next_version, record.created_by, "metadata label assignment")
        return record

    def assign_alias(self, name: str, alias: str, version: int, updated_by: str, reason: str) -> PromptAlias:
        record = PromptAlias(name=name, alias=alias, version=version, updated_by=updated_by, reason=reason)
        self.metadata_store.upsert_alias(record)
        self.artifact_store.write_json(f"registry/{name}/aliases/{alias}.json", record.model_dump(mode="json"))
        return record

    def resolve(self, reference: str) -> PromptVersion:
        if "@" in reference:
            name, alias = reference.split("@", 1)
            alias_record = self.metadata_store.get_alias(name, alias)
            if alias_record is None:
                raise KeyError(f"Alias not found: {reference}")
            version_record = self.metadata_store.get_prompt_version(name, alias_record.version)
            if version_record is None:
                raise KeyError(f"Version not found for alias: {reference}")
            return version_record
        if ":" in reference:
            name, version = reference.split(":", 1)
            version_record = self.metadata_store.get_prompt_version(name, int(version))
            if version_record is None:
                raise KeyError(f"Version not found: {reference}")
            return version_record
        versions = self.metadata_store.list_prompt_versions(reference)
        if not versions:
            raise KeyError(f"Prompt not found: {reference}")
        return versions[-1]

    def diff(self, name: str, from_version: int, to_version: int) -> dict[str, Any]:
        left = self.metadata_store.get_prompt_version(name, from_version)
        right = self.metadata_store.get_prompt_version(name, to_version)
        if left is None or right is None:
            raise KeyError(f"Missing prompt versions for diff: {name} {from_version}->{to_version}")
        template_diff = "\n".join(
            unified_diff(
                left.definition.template.splitlines(),
                right.definition.template.splitlines(),
                fromfile=f"{name}@{from_version}",
                tofile=f"{name}@{to_version}",
                lineterm="",
            )
        )
        return {
            "from_version": from_version,
            "to_version": to_version,
            "template_diff": template_diff,
            "metadata_changed": left.definition.metadata.model_dump() != right.definition.metadata.model_dump(),
            "variables_changed": left.definition.variables != right.definition.variables,
        }

    def search(self, query: str = "") -> list[RegistrySearchResult]:
        rows = self.metadata_store.conn.execute("select distinct name from prompt_versions").fetchall()
        names = sorted(row["name"] for row in rows)
        matches: list[RegistrySearchResult] = []
        for name in names:
            if query and query.lower() not in name.lower():
                continue
            versions = [record.version for record in self.metadata_store.list_prompt_versions(name)]
            aliases = {record.alias: record.version for record in self.metadata_store.list_aliases(name)}
            matches.append(RegistrySearchResult(name=name, versions=versions, aliases=aliases))
        return matches

    def rollback_alias(self, name: str, alias: str, version: int, updated_by: str) -> PromptAlias:
        return self.assign_alias(name, alias, version, updated_by, "rollback")
