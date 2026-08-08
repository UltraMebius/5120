"""Temporary sensory-level behaviour for the mock route flow."""

from typing import Literal

SensoryLevel = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]


def get_mock_sensory_level(route_id: str) -> SensoryLevel:
    """Return a fixed mock label for the two temporary route examples."""
    # TODO: Define real calculations and thresholds only after the processed
    # pedestrian data has been analysed and documented by the team.
    mock_levels: dict[str, SensoryLevel] = {
        "route-a": "LOW",
        "route-b": "HIGH",
    }
    return mock_levels.get(route_id, "UNKNOWN")
