import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import { useJourney } from "../context/JourneyContext";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";

function ArrivalPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const [isEnding, setIsEnding] = useState(false);
  const route = journey.selectedRoute;

  if ((!route || !journey.destination) && !isEnding) {
    return <Navigate replace to="/routes/search" />;
  }

  if (!route || !journey.destination) {
    return null;
  }

  function endNavigation() {
    setIsEnding(true);
    journey.resetJourney();
    navigate(APP_CONFIG.homeRoute, { replace: true });
  }

  return (
    <main className="arrival-page">
      <section className="arrival-card">
        <div className="arrival-card__mark" aria-hidden="true">
          ✓
        </div>
        <p className="eyebrow">Planned journey</p>
        <h1>Route summary</h1>
        <p className="arrival-card__destination">
          {journey.destination.label}
        </p>

        <div className="arrival-stats">
          <div>
            <span>Planned distance</span>
            <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
          </div>
          <div>
            <span>Estimated time</span>
            <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
          </div>
          <div>
            <span>Route roles</span>
            <strong>{route.roleBadges.join(" + ")}</strong>
          </div>
        </div>

        <p className="arrival-note">
          This summary reflects the planned route. Live route progress and
          actual journey time were not tracked.
        </p>

        <button
          className="button button--primary button--large button--full"
          onClick={endNavigation}
          type="button"
        >
          End navigation
        </button>
      </section>
    </main>
  );
}

export default ArrivalPage;
