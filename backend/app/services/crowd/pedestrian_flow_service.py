"""Source-separated point pedestrian flow using batched sensor evidence."""

from collections.abc import Callable, Sequence
import math

from ...config import SETTINGS
from ...models.pedestrian_flow import (
    FlowSamplePoint,
    PedestrianFlowBatchEvaluation,
    PedestrianFlowContribution,
    SamplePedestrianFlow,
    SensorPedestrianFlow,
)
from ...repositories.pedestrian_flow_repository import PedestrianFlowRepository
from .spatial_crowd_service import (
    coverage_for_distance,
    inverse_distance_weights,
)


class PedestrianFlowDataConsistencyError(RuntimeError):
    """Batched current or baseline evidence cannot be combined safely."""


class PedestrianFlowService:
    """Calculate live and historical point flow without mixing their sources."""

    def __init__(
        self,
        repository: PedestrianFlowRepository | None = None,
        *,
        core_radius_m: float = SETTINGS.spatial.core_support_radius_m,
        maximum_radius_m: float = SETTINGS.spatial.max_support_radius_m,
        weighting_power: int = SETTINGS.spatial.weighting_power,
        distance_floor_m: float = SETTINGS.spatial.distance_floor_m,
    ) -> None:
        if core_radius_m <= 0.0 or maximum_radius_m < core_radius_m:
            raise ValueError("pedestrian-flow spatial radii are invalid")
        if weighting_power != 1:
            raise ValueError("pedestrian flow requires inverse-distance power 1")
        if distance_floor_m != 1.0:
            raise ValueError("pedestrian flow requires a 1 metre distance floor")
        self.repository = repository or PedestrianFlowRepository()
        self.core_radius_m = float(core_radius_m)
        self.maximum_radius_m = float(maximum_radius_m)
        self.weighting_power = weighting_power
        self.distance_floor_m = float(distance_floor_m)

    def _usable_sensors(
        self,
        sensors: Sequence[SensorPedestrianFlow],
        value_getter: Callable[[SensorPedestrianFlow], float | None],
    ) -> tuple[tuple[SensorPedestrianFlow, float], ...]:
        usable: list[tuple[SensorPedestrianFlow, float]] = []
        for sensor in sensors:
            if (
                not math.isfinite(sensor.distance_meters)
                or sensor.distance_meters < 0.0
            ):
                raise PedestrianFlowDataConsistencyError(
                    "sensor distances must be finite and non-negative"
                )
            if sensor.distance_meters > self.maximum_radius_m:
                continue
            if not sensor.active_outdoor:
                continue
            value = value_getter(sensor)
            if value is None:
                continue
            if not math.isfinite(value) or value < 0.0:
                raise PedestrianFlowDataConsistencyError(
                    "pedestrian-flow rates must be finite and non-negative"
                )
            usable.append((sensor, value))
        return tuple(
            sorted(
                usable,
                key=lambda item: (
                    item[0].distance_meters,
                    item[0].location_id,
                ),
            )
        )

    def _weighted_flow(
        self,
        usable: Sequence[tuple[SensorPedestrianFlow, float]],
    ) -> tuple[float | None, tuple[PedestrianFlowContribution, ...]]:
        if not usable:
            return None, ()
        distances = tuple(sensor.distance_meters for sensor, _ in usable)
        weights = inverse_distance_weights(
            distances,
            power=self.weighting_power,
            distance_floor_m=self.distance_floor_m,
        )
        contributions = tuple(
            PedestrianFlowContribution(
                location_id=sensor.location_id,
                distance_meters=sensor.distance_meters,
                normalised_weight=weight,
                pedestrian_movements_per_minute=value,
            )
            for (sensor, value), weight in zip(usable, weights)
        )
        return (
            sum(
                row.pedestrian_movements_per_minute * row.normalised_weight
                for row in contributions
            ),
            contributions,
        )

    def evaluate_samples(
        self,
        samples: Sequence[FlowSamplePoint],
    ) -> PedestrianFlowBatchEvaluation:
        """Evaluate every route/sample key through one repository batch call."""

        batch = self.repository.find_flow_neighbourhoods(
            samples,
            maximum_radius_m=self.maximum_radius_m,
        )
        if batch.snapshot.window_variant_count > 1:
            raise PedestrianFlowDataConsistencyError(
                "current_sensor_activity contains multiple current windows"
            )

        outputs: list[SamplePedestrianFlow] = []
        for neighbourhood in batch.neighbourhoods:
            live_usable = self._usable_sensors(
                neighbourhood.sensors,
                lambda sensor: (
                    sensor.live_pedestrian_movements_per_minute
                ),
            )
            historical_usable = self._usable_sensors(
                neighbourhood.sensors,
                lambda sensor: (
                    sensor.historical_typical_movements_per_minute
                ),
            )
            live_value, live_contributions = self._weighted_flow(live_usable)
            historical_value, historical_contributions = self._weighted_flow(
                historical_usable
            )
            nearest_live = (
                live_usable[0][0].distance_meters if live_usable else None
            )
            nearest_historical = (
                historical_usable[0][0].distance_meters
                if historical_usable
                else None
            )
            sample = neighbourhood.sample
            outputs.append(
                SamplePedestrianFlow(
                    route_index=sample.route_index,
                    sample_index=sample.sample_index,
                    distance_along_route_meters=(
                        sample.distance_along_route_meters
                    ),
                    live_support_status=coverage_for_distance(
                        nearest_live,
                        core_radius_m=self.core_radius_m,
                        maximum_radius_m=self.maximum_radius_m,
                    ),
                    historical_support_status=coverage_for_distance(
                        nearest_historical,
                        core_radius_m=self.core_radius_m,
                        maximum_radius_m=self.maximum_radius_m,
                    ),
                    live_pedestrian_movements_per_minute=live_value,
                    historical_typical_movements_per_minute=historical_value,
                    live_contributor_count=len(live_usable),
                    historical_contributor_count=len(historical_usable),
                    nearest_live_sensor_distance_meters=nearest_live,
                    nearest_historical_sensor_distance_meters=(
                        nearest_historical
                    ),
                    window_start=batch.snapshot.window_start,
                    window_end=batch.snapshot.window_end,
                    calculated_at=batch.snapshot.calculated_at,
                    baseline_hour_day=batch.snapshot.baseline_hour_day,
                    baseline_day_type=batch.snapshot.baseline_day_type,
                    live_contributions=live_contributions,
                    historical_contributions=historical_contributions,
                )
            )

        return PedestrianFlowBatchEvaluation(
            samples=tuple(outputs),
            snapshot=batch.snapshot,
            flow_batch_db_ms=batch.database_elapsed_ms,
            sql_execution_count=batch.sql_execution_count,
        )
