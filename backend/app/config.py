"""Environment-backed application and frozen Epic 1 handoff configuration."""

from dataclasses import dataclass, field
import os


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return float(raw_value)


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return int(raw_value)


def _read_origins() -> tuple[str, ...]:
    raw_value = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())


@dataclass(frozen=True)
class CrowdBandSettings:
    """Confirmed relative Network percentile band boundaries."""

    very_low_max: float = 25.0
    low_max: float = 50.0
    moderate_max: float = 75.0
    high_max: float = 90.0


@dataclass(frozen=True)
class CrowdPreferenceSettings:
    """Configurable product preferences; these are not clinical thresholds."""

    avoid_busy_max_score: float = field(
        default_factory=lambda: _read_float(
            "AVOID_BUSY_MAX_PREFERRED_SCORE", 50.0
        )
    )
    prefer_quieter_max_score: float = field(
        default_factory=lambda: _read_float(
            "PREFER_QUIETER_MAX_PREFERRED_SCORE", 75.0
        )
    )
    flexible_max_score: float = field(
        default_factory=lambda: _read_float(
            "FLEXIBLE_MAX_PREFERRED_SCORE", 90.0
        )
    )


@dataclass(frozen=True)
class SpatialSettings:
    """Confirmed spatial support contract from handoff V3."""

    core_support_radius_m: int = field(
        default_factory=lambda: _read_int("CORE_SPATIAL_SUPPORT_RADIUS_M", 250)
    )
    max_support_radius_m: int = field(
        default_factory=lambda: _read_int("MAX_SPATIAL_SUPPORT_RADIUS_M", 300)
    )
    weighting_method: str = field(
        default_factory=lambda: os.getenv(
            "SPATIAL_WEIGHT_METHOD", "inverse_distance"
        )
    )
    weighting_power: int = field(
        default_factory=lambda: _read_int("SPATIAL_WEIGHT_POWER", 1)
    )
    distance_floor_m: int = field(
        default_factory=lambda: _read_int("SPATIAL_DISTANCE_FLOOR_M", 1)
    )


@dataclass(frozen=True)
class RouteSettings:
    """Route scoring/ranking configuration to be implemented after Phase 1."""

    sample_interval_m: int = field(
        default_factory=lambda: _read_int("ROUTE_SAMPLE_INTERVAL_M", 50)
    )
    summary_method: str = "P75_crowd_exposure_score"
    ranking_order: tuple[str, ...] = (
        "no_data_pct ASC",
        "pct_above_preference ASC",
        "p75_crowd_exposure_score ASC",
        "maximum_crowd_exposure_score ASC",
        "duration_seconds ASC",
    )


@dataclass(frozen=True)
class Settings:
    app_title: str = "CalmWay API"
    app_description: str = (
        "Phase 1 API scaffold for CalmWay crowd-aware walking routes."
    )
    app_timezone: str = field(
        default_factory=lambda: os.getenv("APP_TIMEZONE", "Australia/Melbourne")
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )
    frontend_origins: tuple[str, ...] = field(default_factory=_read_origins)
    mapbox_access_token: str = field(
        default_factory=lambda: os.getenv("MAPBOX_ACCESS_TOKEN", "")
    )
    bands: CrowdBandSettings = field(default_factory=CrowdBandSettings)
    preferences: CrowdPreferenceSettings = field(
        default_factory=CrowdPreferenceSettings
    )
    spatial: SpatialSettings = field(default_factory=SpatialSettings)
    route: RouteSettings = field(default_factory=RouteSettings)


SETTINGS = Settings()

# Compatibility exports keep the small existing FastAPI bootstrap straightforward.
APP_TITLE = SETTINGS.app_title
APP_DESCRIPTION = SETTINGS.app_description
FRONTEND_ORIGINS = list(SETTINGS.frontend_origins)
