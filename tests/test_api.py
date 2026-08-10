from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_backend_api_contract_paths_remain_available() -> None:
    paths = app.openapi()["paths"]

    assert "get" in paths["/health"]
    assert client.get("/docs").status_code == 200
    assert "get" in paths["/api/v1/crowd/point"]
    assert "post" in paths["/api/v1/routes/walking"]


def test_walking_route_cors_preflight_allows_local_frontend() -> None:
    response = client.options(
        "/api/v1/routes/walking",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "POST" in response.headers["access-control-allow-methods"]
