from fastapi.testclient import TestClient

from app.main import create_app


def test_app_exposes_healthz_when_bootstrap_failed():
    app = create_app(services={}, bootstrap_error="Qdrant dimension mismatch")
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert "Qdrant dimension mismatch" in response.json()["detail"]


def test_bootstrap_failure_renders_diagnostic_page():
    app = create_app(services={}, bootstrap_error="Qdrant dimension mismatch")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 503
    assert "系统初始化失败" in response.text
    assert "Qdrant dimension mismatch" in response.text
