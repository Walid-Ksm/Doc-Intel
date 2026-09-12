"""Unit tests for the /health liveness probe.

No infrastructure dependencies — the probe must return 200 whether or not
Postgres or MinIO are reachable.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_body():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_requires_no_auth():
    """Health probe must be reachable without any Authorization header."""
    response = client.get("/health")
    # 401/403 would mean auth is incorrectly applied to this endpoint.
    assert response.status_code != 401
    assert response.status_code != 403
