"""Deprecated compatibility shim for the original mock sensory service."""

from typing import Literal

from ..models.crowd import CrowdLevel
from .crowd.presentation import to_frontend_crowd_level

SensoryLevel = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]


def get_mock_sensory_level(route_id: str) -> SensoryLevel:
    """Preserve existing tests while presenting only the three UI levels."""
    mock_internal_levels = {
        "route-a": CrowdLevel.LOW,
        "route-b": CrowdLevel.HIGH,
    }
    internal_level = mock_internal_levels.get(route_id)
    if internal_level is None:
        return "UNKNOWN"
    return to_frontend_crowd_level(internal_level).value
