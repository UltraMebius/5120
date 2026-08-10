from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from backend.app.api.internal import (
    get_current_activity_refresh_service,
    get_refresh_secret,
)
from backend.app.main import app
from backend.app.services.ingestion.current_activity_refresh import (
    CurrentActivityRefreshService,
)


ENDPOINT = "/api/v1/internal/refresh-current-activity"
TEST_REFRESH_SECRET = "test-only-placeholder-refresh-secret"


@pytest.fixture
def refresh_api():
    service = MagicMock(spec=CurrentActivityRefreshService)
    service.refresh.return_value = SimpleNamespace(current_rows_written=134)
    app.dependency_overrides[get_refresh_secret] = lambda: TEST_REFRESH_SECRET
    app.dependency_overrides[get_current_activity_refresh_service] = (
        lambda: service
    )
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.pop(get_refresh_secret, None)
        app.dependency_overrides.pop(
            get_current_activity_refresh_service,
            None,
        )


def test_refresh_rejects_missing_authorization(refresh_api) -> None:
    client, service = refresh_api

    response = client.post(ENDPOINT)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert TEST_REFRESH_SECRET not in response.text
    service.refresh.assert_not_called()


@pytest.mark.parametrize(
    "authorization",
    ["Basic placeholder", "Bearer", "Bearer too many parts"],
)
def test_refresh_rejects_malformed_bearer_authorization(
    refresh_api,
    authorization: str,
) -> None:
    client, service = refresh_api

    response = client.post(
        ENDPOINT,
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401
    assert TEST_REFRESH_SECRET not in response.text
    service.refresh.assert_not_called()


def test_refresh_rejects_wrong_secret(refresh_api) -> None:
    client, service = refresh_api
    provided_secret = "wrong-placeholder-secret"

    response = client.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {provided_secret}"},
    )

    assert response.status_code == 403
    assert TEST_REFRESH_SECRET not in response.text
    assert provided_secret not in response.text
    service.refresh.assert_not_called()


def test_refresh_fails_closed_when_secret_is_not_configured(refresh_api) -> None:
    client, service = refresh_api
    app.dependency_overrides[get_refresh_secret] = lambda: ""

    response = client.post(
        ENDPOINT,
        headers={"Authorization": "Bearer placeholder"},
    )

    assert response.status_code == 503
    assert TEST_REFRESH_SECRET not in response.text
    service.refresh.assert_not_called()


def test_refresh_calls_existing_service_once_with_correct_secret(
    refresh_api,
) -> None:
    client, service = refresh_api

    response = client.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {TEST_REFRESH_SECRET}"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "updated": 134}
    assert TEST_REFRESH_SECRET not in response.text
    service.refresh.assert_called_once()
    keyword_arguments = service.refresh.call_args.kwargs
    assert keyword_arguments["dry_run"] is False
    assert keyword_arguments["as_of"].utcoffset() is not None


def test_refresh_service_failure_returns_sanitized_error(refresh_api) -> None:
    client, service = refresh_api
    private_error = f"database details and {TEST_REFRESH_SECRET}"
    service.refresh.side_effect = RuntimeError(private_error)

    response = client.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {TEST_REFRESH_SECRET}"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Current activity refresh failed."}
    assert private_error not in response.text
    assert TEST_REFRESH_SECRET not in response.text
    service.refresh.assert_called_once()
