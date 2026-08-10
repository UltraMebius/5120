"""Presentation-only mapping from five backend levels to three UI levels."""

from ...models.crowd import CrowdLevel, FrontendCrowdLevel


def to_frontend_crowd_level(level: CrowdLevel) -> FrontendCrowdLevel:
    if level in (CrowdLevel.VERY_LOW, CrowdLevel.LOW):
        return FrontendCrowdLevel.LOW
    if level is CrowdLevel.MODERATE:
        return FrontendCrowdLevel.MEDIUM
    return FrontendCrowdLevel.HIGH
