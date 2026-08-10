from backend.app.config import SETTINGS
from backend.app.models.crowd import CrowdLevel, FrontendCrowdLevel
from backend.app.services.crowd.presentation import to_frontend_crowd_level


def test_five_backend_levels_map_only_at_the_presentation_boundary() -> None:
    assert to_frontend_crowd_level(CrowdLevel.VERY_LOW) is FrontendCrowdLevel.LOW
    assert to_frontend_crowd_level(CrowdLevel.LOW) is FrontendCrowdLevel.LOW
    assert (
        to_frontend_crowd_level(CrowdLevel.MODERATE)
        is FrontendCrowdLevel.MEDIUM
    )
    assert to_frontend_crowd_level(CrowdLevel.HIGH) is FrontendCrowdLevel.HIGH
    assert (
        to_frontend_crowd_level(CrowdLevel.VERY_HIGH)
        is FrontendCrowdLevel.HIGH
    )


def test_phase_one_defaults_preserve_handoff_configuration() -> None:
    assert SETTINGS.preferences.avoid_busy_max_score == 50
    assert SETTINGS.preferences.prefer_quieter_max_score == 75
    assert SETTINGS.preferences.flexible_max_score == 90
    assert SETTINGS.spatial.core_support_radius_m == 250
    assert SETTINGS.spatial.max_support_radius_m == 300
    assert SETTINGS.spatial.weighting_method == "inverse_distance"
    assert SETTINGS.spatial.weighting_power == 1
    assert SETTINGS.spatial.distance_floor_m == 1
    assert SETTINGS.route.sample_interval_m == 50
    assert SETTINGS.route.minimum_crowd_coverage_pct == 55
    assert SETTINGS.route.summary_method == "P75_crowd_exposure_score"
    assert SETTINGS.route.ranking_order == (
        "no_data_pct ASC",
        "pct_above_preference ASC",
        "p75_crowd_exposure_score ASC",
        "maximum_crowd_exposure_score ASC",
        "duration_seconds ASC",
        "route_index ASC",
    )
