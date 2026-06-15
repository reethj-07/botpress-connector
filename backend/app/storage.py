import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import NullPool

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///"):
        path = database_url.replace("sqlite:///", "", 1)
        parent = Path(path).expanduser().resolve().parent
        parent.mkdir(parents=True, exist_ok=True)
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
    return create_engine(database_url)


class Store:
    def __init__(self, database_url: str) -> None:
        self.engine = configure_engine(database_url)
        self.init()

    def connect(self) -> Connection:
        return self.engine.begin()

    def init(self) -> None:
        with self.connect() as conn:
            conn.execute(text(
                """
                create table if not exists resources (
                    id text primary key,
                    account_name text not null,
                    resource_name text not null,
                    webhook_id text not null,
                    encryption_key text,
                    user_id text,
                    description text,
                    validation_status text not null default 'not_validated',
                    last_validated_at text,
                    created_at text not null,
                    updated_at text not null
                );
                """
            ))
            conn.execute(text(
                """
                create table if not exists scan_runs (
                    id text primary key,
                    resource_id text not null references resources(id),
                    created_at text not null
                );
                """
            ))
            conn.execute(text(
                """
                create table if not exists scan_results (
                    id text primary key,
                    scan_run_id text not null references scan_runs(id),
                    resource_id text not null references resources(id),
                    vulnerability_id text not null,
                    attack_id text not null,
                    test_input text not null,
                    success integer not null,
                    model_response text,
                    execution_time_ms integer not null,
                    error text,
                    metadata_json text not null,
                    created_at text not null
                );
                """
            ))

    def create_resource(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        resource_id = f"res_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute(
                text("""
                insert into resources (
                    id, account_name, resource_name, webhook_id, encryption_key, user_id,
                    description, created_at, updated_at
                ) values (:id, :account_name, :resource_name, :webhook_id, :encryption_key, :user_id, :description, :created_at, :updated_at)
                """),
                {
                    "id": resource_id,
                    "account_name": data["account_name"],
                    "resource_name": data["resource_name"],
                    "webhook_id": data["webhook_id"],
                    "encryption_key": data.get("encryption_key"),
                    "user_id": data.get("user_id"),
                    "description": data.get("description"),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return self.get_resource(resource_id, include_secrets=True)

    def list_resources(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(text("select * from resources order by created_at desc")).mappings().all()
        return [dict(row) for row in rows]

    def get_resource(self, resource_id: str, *, include_secrets: bool = False) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(text("select * from resources where id = :id"), {"id": resource_id}).mappings().fetchone()
        if not row:
            raise KeyError(resource_id)
        data = dict(row)
        if not include_secrets:
            data["encryption_key"] = None
        return data

    def update_validation(self, resource_id: str, status: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                text("update resources set validation_status = :status, last_validated_at = :last_validated_at, updated_at = :updated_at where id = :id"),
                {"status": status, "last_validated_at": now, "updated_at": now, "id": resource_id},
            )
        return self.get_resource(resource_id)

    def create_scan_run(self, resource_id: str, prompts: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
        now = utc_now()
        scan_run_id = f"scan_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute(text("insert into scan_runs (id, resource_id, created_at) values (:id, :resource_id, :created_at)"), {"id": scan_run_id, "resource_id": resource_id, "created_at": now})
            for prompt, result in zip(prompts, results):
                conn.execute(
                    text("""
                    insert into scan_results (
                        id, scan_run_id, resource_id, vulnerability_id, attack_id, test_input,
                        success, model_response, execution_time_ms, error, metadata_json, created_at
                    ) values (:id, :scan_run_id, :resource_id, :vulnerability_id, :attack_id, :test_input, :success, :model_response, :execution_time_ms, :error, :metadata_json, :created_at)
                    """),
                    {
                        "id": f"sr_{uuid.uuid4().hex[:12]}",
                        "scan_run_id": scan_run_id,
                        "resource_id": resource_id,
                        "vulnerability_id": result["vulnerability_id"],
                        "attack_id": result["attack_id"],
                        "test_input": prompt["test_input"],
                        "success": 1 if result["success"] else 0,
                        "model_response": result.get("model_response"),
                        "execution_time_ms": result["execution_time_ms"],
                        "error": result.get("error"),
                        "metadata_json": json.dumps(result.get("metadata") or {}),
                        "created_at": now,
                    },
                )
        return self.get_scan_run(scan_run_id)

    def get_scan_run(self, scan_run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute(text("select * from scan_runs where id = :id"), {"id": scan_run_id}).mappings().fetchone()
            rows = conn.execute(text("select * from scan_results where scan_run_id = :scan_run_id order by created_at asc"), {"scan_run_id": scan_run_id}).mappings().all()
        if not run:
            raise KeyError(scan_run_id)
        return {"id": run["id"], "resource_id": run["resource_id"], "created_at": run["created_at"], "results": [self._scan_result(row) for row in rows]}

    def list_scans(self, resource_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            runs = conn.execute(text("select * from scan_runs where resource_id = :resource_id order by created_at desc"), {"resource_id": resource_id}).mappings().all()
        return [self.get_scan_run(row["id"]) for row in runs]

    def _scan_result(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["success"] = bool(data["success"])
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data
