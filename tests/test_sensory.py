from backend.app.services.sensory_service import get_mock_sensory_level


def test_mock_sensory_levels_are_explicit() -> None:
    assert get_mock_sensory_level("route-a") == "LOW"
    assert get_mock_sensory_level("route-b") == "HIGH"
    assert get_mock_sensory_level("unconfigured-route") == "UNKNOWN"
