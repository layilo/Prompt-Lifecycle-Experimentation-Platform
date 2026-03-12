from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from prompt_platform.schemas import (
    DeploymentRecord,
    EvaluationResult,
    PromptAlias,
    PromptChangeRecord,
    PromptVersion,
    PromotionDecision,
)
from prompt_platform.utils import dump_json, ensure_dir, load_json


class FileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = ensure_dir(root)

    def write_json(self, relative_path: str, payload: Any) -> Path:
        path = self.root / relative_path
        ensure_dir(path.parent)
        dump_json(path, payload)
        return path

    def read_json(self, relative_path: str) -> Any:
        return load_json(self.root / relative_path)


class SQLiteMetadataStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        ensure_dir(db_path.parent)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            create table if not exists prompt_versions (
                name text not null,
                version integer not null,
                payload text not null,
                primary key (name, version)
            );
            create table if not exists prompt_aliases (
                name text not null,
                alias text not null,
                payload text not null,
                primary key (name, alias)
            );
            create table if not exists change_records (
                name text not null,
                version integer not null,
                payload text not null,
                primary key (name, version)
            );
            create table if not exists evaluation_results (
                run_id text primary key,
                prompt_name text not null,
                version integer not null,
                payload text not null
            );
            create table if not exists promotion_decisions (
                prompt_name text not null,
                candidate_version integer not null,
                payload text not null,
                primary key (prompt_name, candidate_version)
            );
            create table if not exists deployment_records (
                prompt_name text not null,
                alias text not null,
                version integer not null,
                payload text not null,
                primary key (prompt_name, alias, version)
            );
            """
        )
        self.conn.commit()

    def upsert_prompt_version(self, record: PromptVersion) -> None:
        self.conn.execute(
            "insert or replace into prompt_versions(name, version, payload) values (?, ?, ?)",
            (record.name, record.version, record.model_dump_json()),
        )
        self.conn.commit()

    def get_prompt_version(self, name: str, version: int) -> Optional[PromptVersion]:
        row = self.conn.execute(
            "select payload from prompt_versions where name = ? and version = ?",
            (name, version),
        ).fetchone()
        return PromptVersion.model_validate_json(row["payload"]) if row else None

    def list_prompt_versions(self, name: str) -> list[PromptVersion]:
        rows = self.conn.execute(
            "select payload from prompt_versions where name = ? order by version",
            (name,),
        ).fetchall()
        return [PromptVersion.model_validate_json(row["payload"]) for row in rows]

    def upsert_alias(self, record: PromptAlias) -> None:
        self.conn.execute(
            "insert or replace into prompt_aliases(name, alias, payload) values (?, ?, ?)",
            (record.name, record.alias, record.model_dump_json()),
        )
        self.conn.commit()

    def get_alias(self, name: str, alias: str) -> Optional[PromptAlias]:
        row = self.conn.execute(
            "select payload from prompt_aliases where name = ? and alias = ?",
            (name, alias),
        ).fetchone()
        return PromptAlias.model_validate_json(row["payload"]) if row else None

    def list_aliases(self, name: str) -> list[PromptAlias]:
        rows = self.conn.execute(
            "select payload from prompt_aliases where name = ? order by alias",
            (name,),
        ).fetchall()
        return [PromptAlias.model_validate_json(row["payload"]) for row in rows]

    def write_change_record(self, record: PromptChangeRecord) -> None:
        self.conn.execute(
            "insert or replace into change_records(name, version, payload) values (?, ?, ?)",
            (record.name, record.version, record.model_dump_json()),
        )
        self.conn.commit()

    def write_evaluation_result(self, result: EvaluationResult) -> None:
        self.conn.execute(
            "insert or replace into evaluation_results(run_id, prompt_name, version, payload) values (?, ?, ?, ?)",
            (result.run_id, result.prompt_name, result.version, result.model_dump_json()),
        )
        self.conn.commit()

    def get_evaluation_result(self, run_id: str) -> Optional[EvaluationResult]:
        row = self.conn.execute(
            "select payload from evaluation_results where run_id = ?",
            (run_id,),
        ).fetchone()
        return EvaluationResult.model_validate_json(row["payload"]) if row else None

    def write_promotion_decision(self, decision: PromotionDecision) -> None:
        self.conn.execute(
            "insert or replace into promotion_decisions(prompt_name, candidate_version, payload) values (?, ?, ?)",
            (decision.prompt_name, decision.candidate_version, decision.model_dump_json()),
        )
        self.conn.commit()

    def write_deployment_record(self, record: DeploymentRecord) -> None:
        self.conn.execute(
            "insert or replace into deployment_records(prompt_name, alias, version, payload) values (?, ?, ?, ?)",
            (record.prompt_name, record.alias, record.version, record.model_dump_json()),
        )
        self.conn.commit()
