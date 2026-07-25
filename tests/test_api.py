from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from datacopilot import api
from datacopilot.config import settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Point the app at a throwaway DB before the lifespan seeds it.
    settings.db_path = str(tmp_path_factory.mktemp("api_db") / "api.db")
    with TestClient(api.app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz(client):
    body = client.get("/readyz").json()
    assert body["status"] == "ready"


def test_schema_endpoint(client):
    body = client.get("/schema").json()
    assert "students" in body["schema"]


def test_query_success(client):
    body = client.post("/query", json={"question": "How many students are there?"}).json()
    assert body["status"] == "success"
    assert body["row_count"] == 1


def test_query_refusal(client):
    body = client.post("/query", json={"question": "capital of France?"}).json()
    assert body["status"] == "refused"


def test_query_validation_rejects_empty(client):
    resp = client.post("/query", json={"question": ""})
    assert resp.status_code == 422  # pydantic min_length
