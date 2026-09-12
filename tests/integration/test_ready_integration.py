"""Integration tests for the /ready readiness probe.

Requires real Postgres and MinIO to be running (same fixtures used by the
rest of the integration suite).  The test verifies the happy-path contract:
both dependencies reachable → HTTP 200 with the expected JSON body.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_returns_200_when_dependencies_are_up():
    """Both Postgres and MinIO are running in the integration environment."""
    response = client.get("/ready")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        f"Response body: {response.text}"
    )


def test_ready_body_reports_both_dependencies_ok():
    response = client.get("/ready")
    data = response.json()
    assert data["status"] == "ready"
    assert data["postgres"] == "ok"
    assert data["minio"] == "ok"


def test_ready_requires_no_auth():
    """Readiness probe must be reachable without any Authorization header."""
    response = client.get("/ready")
    assert response.status_code != 401
    assert response.status_code != 403
