import SensoryBadge from "./SensoryBadge";
import type { Route } from "../types/route";

interface RouteCardProps {
  route: Route;
}

function RouteCard({ route }: RouteCardProps) {
  return (
    <article className={`route-card${route.recommended ? " recommended" : ""}`}>
      <div className="route-card-heading">
        <h3>{route.name}</h3>
        {route.recommended && <span className="recommended-label">Recommended</span>}
      </div>
      <dl>
        <div>
          <dt>Distance</dt>
          <dd>{route.distanceKm.toFixed(1)} km</dd>
        </div>
        <div>
          <dt>Walking time</dt>
          <dd>{route.durationMin} min</dd>
        </div>
        <div>
          <dt>Sensory level</dt>
          <dd>
            <SensoryBadge level={route.sensoryLevel} />
          </dd>
        </div>
      </dl>
    </article>
  );
}

export default RouteCard;
