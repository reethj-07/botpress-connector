import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_resource_lifecycle():
    db_path = Path("test_api.sqlite3")
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200

    created = client.post(
        "/api/v1/resources",
        json={
            "account_name": "Eval",
            "resource_name": "Demo Bot",
            "webhook_id": "abc123456789",
            "encryption_key": "do-not-return",
        },
    )
    assert created.status_code == 201
    resource = created.json()
    assert resource["webhook_id"] == "abc1...6789"
    assert resource["encryption_key"] is None

    listed = client.get("/api/v1/resources")
    assert listed.status_code == 200
    assert listed.json()["resources"][0]["id"] == resource["id"]
    if db_path.exists():
        db_path.unlink()
