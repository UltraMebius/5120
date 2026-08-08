from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_route_endpoint_returns_mock_routes() -> None:
    response = client.get("/api/routes")

    assert response.status_code == 200
    routes = response.json()
    assert len(routes) >= 2
    assert routes[0]["sensoryLevel"] in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
