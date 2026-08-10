import type { WalkingRoute } from "../../types/route";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../../utils/formatRoute";

interface RouteCardProps {
  isPreviewed: boolean;
  onDepart: (route: WalkingRoute) => void;
  onPreview: (route: WalkingRoute) => void;
  route: WalkingRoute;
}

function RouteCard({
  isPreviewed,
  onDepart,
  onPreview,
  route,
}: RouteCardProps) {
  return (
    <article
      className={`route-card${isPreviewed ? " route-card--previewed" : ""}`}
    >
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

      <div className="route-card__actions">
        <button
          aria-pressed={isPreviewed}
          className="button button--secondary"
          onClick={() => onPreview(route)}
          type="button"
        >
          {isPreviewed ? "Shown on map" : "Preview on map"}
        </button>
        <button
          className="button button--primary"
          onClick={() => onDepart(route)}
          type="button"
        >
          Depart
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </article>
  );
}

export default RouteCard;
