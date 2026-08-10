"""Authoritative 250/300 m point support and normalised inverse-distance scoring."""

from collections.abc import Sequence
import math

from ...config import SETTINGS
from ...models.crowd import CoverageStatus, DataState
from ...models.spatial import (
    PointCrowdEstimate,
    SpatialContribution,
    SpatialNeighbourhood,
    SpatialSensorCandidate,
)
from ...repositories.spatial_repository import SpatialRepository
from .current_activity_service import (
    classify_crowd_level,
    classify_local_condition,
)


WEIGHTING_METHOD_NAME = "inverse_distance_1_over_d"


class CoordinateValidationError(ValueError):
    """A query coordinate is not a finite WGS84 longitude/latitude value."""


class SpatialDataConsistencyError(RuntimeError):
    """Materialised current inputs cannot safely be combined."""


def validate_coordinates(*, longitude: float, latitude: float) -> None:
    if isinstance(longitude, bool) or not math.isfinite(longitude):
        raise CoordinateValidationError("longitude must be a finite number")
    if isinstance(latitude, bool) or not math.isfinite(latitude):
        raise CoordinateValidationError("latitude must be a finite number")
    if not -180.0 <= longitude <= 180.0:
        raise CoordinateValidationError("longitude must be between -180 and 180")
    if not -90.0 <= latitude <= 90.0:
        raise CoordinateValidationError("latitude must be between -90 and 90")


def inverse_distance_weights(
    distances_m: Sequence[float],
    *,
    power: int,
    distance_floor_m: float,
) -> tuple[float, ...]:
    if power <= 0:
        raise ValueError("power must be positive")
    if distance_floor_m <= 0 or not math.isfinite(distance_floor_m):
        raise ValueError("distance_floor_m must be finite and positive")
    if not distances_m:
        return ()
    raw_weights: list[float] = []
    for distance in distances_m:
        if not math.isfinite(distance) or distance < 0:
            raise ValueError("distances must be finite and non-negative")
        raw_weights.append(1.0 / max(distance, distance_floor_m) ** power)
    total = sum(raw_weights)
    return tuple(weight / total for weight in raw_weights)


def weighted_point_score(
    values: Sequence[float],
    distances_m: Sequence[float],
    *,
    power: int,
    distance_floor_m: float,
) -> float:
    if len(values) != len(distances_m):
        raise ValueError("values and distances_m must have the same length")
    if not values:
        raise ValueError("at least one score is required")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("scores must be finite")
    weights = inverse_distance_weights(
        distances_m,
        power=power,
        distance_floor_m=distance_floor_m,
    )
    return sum(value * weight for value, weight in zip(values, weights))


def coverage_for_distance(
    distance_m: float | None,
    *,
    core_radius_m: float,
    maximum_radius_m: float,
) -> str:
    if distance_m is None or distance_m > maximum_radius_m:
        return CoverageStatus.NO_DATA.value
    if distance_m <= core_radius_m:
        return CoverageStatus.SUPPORTED.value
    return CoverageStatus.LIMITED.value


class SpatialCrowdService:
    def __init__(
        self,
        repository: SpatialRepository | None = None,
        *,
        core_radius_m: float = SETTINGS.spatial.core_support_radius_m,
        maximum_radius_m: float = SETTINGS.spatial.max_support_radius_m,
        weighting_method: str = SETTINGS.spatial.weighting_method,
        weighting_power: int = SETTINGS.spatial.weighting_power,
        distance_floor_m: float = SETTINGS.spatial.distance_floor_m,
    ) -> None:
        if core_radius_m <= 0 or maximum_radius_m < core_radius_m:
            raise ValueError("spatial radii are invalid")
        if weighting_method.strip().casefold() != "inverse_distance":
            raise ValueError("only the adopted inverse_distance method is valid")
        if weighting_power <= 0:
            raise ValueError("weighting_power must be positive")
        if distance_floor_m <= 0:
            raise ValueError("distance_floor_m must be positive")
        self.repository = repository or SpatialRepository()
        self.core_radius_m = float(core_radius_m)
        self.maximum_radius_m = float(maximum_radius_m)
        self.weighting_power = weighting_power
        self.distance_floor_m = float(distance_floor_m)

    @staticmethod
    def _validate_score(value: float, field: str) -> None:
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise SpatialDataConsistencyError(
                f"{field} must be a finite percentile between 0 and 100"
            )

    def _usable_candidates(
        self, candidates: Sequence[SpatialSensorCandidate]
    ) -> tuple[SpatialSensorCandidate, ...]:
        usable: list[SpatialSensorCandidate] = []
        for candidate in candidates:
            if candidate.distance_m > self.maximum_radius_m:
                continue
            if not candidate.active_outdoor:
                continue
            if candidate.data_state != DataState.OK.value:
                continue
            score = candidate.current_15m_network_percentile
            if score is None:
                continue
            self._validate_score(score, "current_15m_network_percentile")
            if candidate.current_1h_local_historical_percentile is not None:
                self._validate_score(
                    candidate.current_1h_local_historical_percentile,
                    "current_1h_local_historical_percentile",
                )
            usable.append(candidate)
        return tuple(sorted(usable, key=lambda row: (row.distance_m, row.location_id)))

    def evaluate(self, *, longitude: float, latitude: float) -> PointCrowdEstimate:
        validate_coordinates(longitude=longitude, latitude=latitude)
        neighbourhood = self.repository.find_neighbourhood(
            longitude=longitude,
            latitude=latitude,
            maximum_radius_m=self.maximum_radius_m,
        )
        return self.evaluate_neighbourhood(
            longitude=longitude,
            latitude=latitude,
            neighbourhood=neighbourhood,
        )

    def evaluate_neighbourhood(
        self,
        *,
        longitude: float,
        latitude: float,
        neighbourhood: SpatialNeighbourhood,
    ) -> PointCrowdEstimate:
        validate_coordinates(longitude=longitude, latitude=latitude)
        if neighbourhood.snapshot.window_variant_count > 1:
            raise SpatialDataConsistencyError(
                "current_sensor_activity contains multiple current windows"
            )

        usable = self._usable_candidates(neighbourhood.candidates)
        if not usable:
            nearest = neighbourhood.nearest_valid_sensor_distance_m
            if nearest is not None and nearest <= self.maximum_radius_m:
                raise SpatialDataConsistencyError(
                    "nearest valid score is inside the radius but absent from "
                    "the PostGIS candidate result"
                )
            active_nearby = [
                row for row in neighbourhood.candidates if row.active_outdoor
            ]
            if active_nearby:
                reason = "NO_VALID_CURRENT_SCORE_WITHIN_MAX_RADIUS"
            elif nearest is not None:
                reason = "NEAREST_VALID_SENSOR_BEYOND_MAX_RADIUS"
            else:
                reason = "NO_VALID_CURRENT_SENSOR_AVAILABLE"
            return PointCrowdEstimate(
                latitude=latitude,
                longitude=longitude,
                crowd_exposure_score=None,
                crowd_level=None,
                local_condition_score=None,
                local_condition=None,
                coverage_status=CoverageStatus.NO_DATA.value,
                nearby_sensors=len(neighbourhood.candidates),
                nearby_active_outdoor_sensors=len(active_nearby),
                supporting_sensors=0,
                nearest_sensor_distance_m=nearest,
                supporting_score_stddev=None,
                weighting_method=WEIGHTING_METHOD_NAME,
                updated_at=neighbourhood.snapshot.updated_at,
                source_window_start=neighbourhood.snapshot.source_window_start,
                source_window_end=neighbourhood.snapshot.source_window_end,
                support_radius_m=self.maximum_radius_m,
                reason=reason,
                contributions=(),
            )

        distances = tuple(row.distance_m for row in usable)
        crowd_scores = tuple(
            float(row.current_15m_network_percentile) for row in usable
        )
        weights = inverse_distance_weights(
            distances,
            power=self.weighting_power,
            distance_floor_m=self.distance_floor_m,
        )
        crowd_score = sum(
            score * weight for score, weight in zip(crowd_scores, weights)
        )

        local_rows = tuple(
            row
            for row in usable
            if row.current_1h_local_historical_percentile is not None
        )
        local_score: float | None = None
        if local_rows:
            local_score = weighted_point_score(
                tuple(
                    float(row.current_1h_local_historical_percentile)
                    for row in local_rows
                ),
                tuple(row.distance_m for row in local_rows),
                power=self.weighting_power,
                distance_floor_m=self.distance_floor_m,
            )

        nearest = distances[0]
        return PointCrowdEstimate(
            latitude=latitude,
            longitude=longitude,
            crowd_exposure_score=crowd_score,
            crowd_level=classify_crowd_level(crowd_score),
            local_condition_score=local_score,
            local_condition=(
                classify_local_condition(local_score)
                if local_score is not None
                else None
            ),
            coverage_status=coverage_for_distance(
                nearest,
                core_radius_m=self.core_radius_m,
                maximum_radius_m=self.maximum_radius_m,
            ),
            nearby_sensors=len(neighbourhood.candidates),
            nearby_active_outdoor_sensors=sum(
                row.active_outdoor for row in neighbourhood.candidates
            ),
            supporting_sensors=len(usable),
            nearest_sensor_distance_m=nearest,
            supporting_score_stddev=None,
            weighting_method=WEIGHTING_METHOD_NAME,
            updated_at=neighbourhood.snapshot.updated_at,
            source_window_start=neighbourhood.snapshot.source_window_start,
            source_window_end=neighbourhood.snapshot.source_window_end,
            support_radius_m=self.maximum_radius_m,
            reason=None,
            contributions=tuple(
                SpatialContribution(
                    location_id=row.location_id,
                    distance_m=row.distance_m,
                    normalised_weight=weight,
                    crowd_exposure_score=float(
                        row.current_15m_network_percentile
                    ),
                    local_condition_score=(
                        None
                        if row.current_1h_local_historical_percentile is None
                        else float(
                            row.current_1h_local_historical_percentile
                        )
                    ),
                )
                for row, weight in zip(usable, weights)
            ),
        )
