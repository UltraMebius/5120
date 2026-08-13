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
  isSelected: boolean;
  onActivate: (route: RouteOption) => void;
  optionNumber: number;
  panelId: string;
  route: RouteOption;
}

function routeLabel(route: RouteOption, optionNumber: number): string {
  return route.roleBadges.length > 0
    ? route.roleBadges.join(" + ")
    : `Route ${optionNumber}`;
}

function RouteCard({
  comparisonBasis,
  isSelected,
  onActivate,
  optionNumber,
  panelId,
  route,
}: RouteCardProps) {
  const label = routeLabel(route, optionNumber);
  const activity = route.relativePedestrianActivity.toLowerCase();

  return (
    <article
      className={`route-card route-card--activity-${activity}${
        isSelected ? " route-card--selected" : ""
      }`}
      data-activity={route.relativePedestrianActivity}
    >
      <button
        aria-controls={panelId}
        aria-selected={isSelected}
        className="route-card__selector"
        id={`route-tab-${route.routeId}`}
        onClick={() => onActivate(route)}
        role="tab"
        type="button"
      >
        <span className="route-card__topline">
          <span className="route-role-badges" aria-label="Route roles">
            {route.roleBadges.length > 0 ? (
              route.roleBadges.map((role) => (
                <span className="route-role-badge" key={role}>
                  {role}
                </span>
              ))
            ) : (
              <span className="route-rank-label">Route {optionNumber}</span>
            )}
          </span>
          <span className="route-card__metric">
            {formatPedestrianActivity(
              route.typicalPedestrianMovementsPerMinute,
              comparisonBasis,
            )}
          </span>
        </span>

        <span className="route-card__secondary">
          <span>{formatWalkingDuration(route.durationSeconds)}</span>
          <span aria-hidden="true">·</span>
          <span>{formatWalkingDistance(route.distanceMeters)}</span>
        </span>
        <span className="route-card__activity">
          {pedestrianActivityLabel(route.relativePedestrianActivity)}
        </span>
        <span className="route-card__source">
          {pedestrianSourceLabel(comparisonBasis)}
        </span>
        <span className="visually-hidden">Select {label} details</span>
      </button>
    </article>
  );
}

export default RouteCard;
