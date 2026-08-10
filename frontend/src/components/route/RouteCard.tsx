import type { WalkingRoute } from "../../types/route";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../../utils/formatRoute";

interface RouteCardProps {
  onDepart: (route: WalkingRoute) => void;
  route: WalkingRoute;
}

function RouteCard({ onDepart, route }: RouteCardProps) {
  return (
    <article className="route-card">
      <div className="route-card__topline">
        <div>
          <span className="route-source-label">Mapbox walking</span>
          <h2>{route.name}</h2>
        </div>
        <span className="crowd-pending-label">Crowd analysis pending</span>
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
            <small>Estimated time</small>
          </span>
        </div>
      </div>

      <button
        className="button button--secondary button--full"
        onClick={() => onDepart(route)}
        type="button"
      >
        Depart
        <span aria-hidden="true">→</span>
      </button>
    </article>
  );
}

export default RouteCard;
