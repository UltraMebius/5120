import type { ComparisonBasis, RouteOption } from "../../types/routeOptions";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../../utils/formatRoute";
import {
  formatPedestrianActivity,
  pedestrianActivityLabel,
  pedestrianSourceLabel,
} from "../../utils/routeOptionPresentation";

interface RouteCardProps {
  comparisonBasis: ComparisonBasis;
  optionNumber: number;
  onSelect: (route: RouteOption) => void;
  route: RouteOption;
}

function RouteCard({
  comparisonBasis,
  optionNumber,
  onSelect,
  route,
}: RouteCardProps) {
  return (
    <article className="route-card">
      <div className="route-card__topline">
        <div>
          <span className="route-source-label">Walking route</span>
          <h2>Option {optionNumber}</h2>
        </div>
        <div aria-label="Route roles" className="route-role-badges">
          {route.roleBadges.map((role) => (
            <span className="route-role-badge" key={role}>
              {role}
            </span>
          ))}
        </div>
      </div>

      <div className="route-card__crowd-analysis">
        <span>
          <strong>
            {formatPedestrianActivity(
              route.typicalPedestrianMovementsPerMinute,
              comparisonBasis,
            )}
          </strong>
          <small>
            {pedestrianActivityLabel(route.relativePedestrianActivity)}
          </small>
          <small>{pedestrianSourceLabel(comparisonBasis)}</small>
        </span>
      </div>

      <div className="route-card__stats">
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ↔
          </span>
          <span>
            <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
            <small>Walking distance</small>
          </span>
        </div>
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ◷
          </span>
          <span>
            <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
            <small>Estimated walking time</small>
          </span>
        </div>
      </div>

      <div className="route-card__actions route-card__actions--single">
        <button
          className="button button--primary"
          onClick={() => onSelect(route)}
          type="button"
        >
          Select route
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </article>
  );
}

export default RouteCard;
