"""Tests E2E del esqueleto inicial y endpoints de Tapaito."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tapaito.api.app import create_app


def test_healthz_and_models() -> None:
    app = create_app()
    client = TestClient(app)

    r_health = client.get("/healthz")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_models = client.get("/v1/models")
    assert r_models.status_code == 200
    data = r_models.json()
    assert data["object"] == "list"
    assert any(m["id"] == "tapaito-mock" for m in data["data"])
