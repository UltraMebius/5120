import type { WalkingRoute } from "../../types/route";
import CrowdBadge from "../crowd/CrowdBadge";

interface RouteCardProps {
  onDepart: (route: WalkingRoute) => void;
  route: WalkingRoute;
}

function RouteCard({ onDepart, route }: RouteCardProps) {
  return (
    <article
      className={`route-card${route.recommended ? " route-card--recommended" : ""}`}
    >
      <div className="route-card__topline">
        <div>
          {route.recommended && (
            <span className="recommended-label">
              <span aria-hidden="true">★</span> CalmWay preview recommendation
            </span>
          )}
          <h2>{route.name}</h2>
        </div>
        <CrowdBadge level={route.crowdLevel} />
      </div>

      <div className="route-card__stats">
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ◇
          </span>
          <span>
            <strong>{route.distanceKm.toFixed(1)} km</strong>
            <small>Walking distance</small>
          </span>
        </div>
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ◷
          </span>
          <span>
            <strong>{route.durationMin} min</strong>
            <small>Estimated time</small>
          </span>
        </div>
      </div>

      <button
        className={`button ${
          route.recommended ? "button--primary" : "button--secondary"
        } button--full`}
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
