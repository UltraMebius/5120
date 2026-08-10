import { Link, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import { useJourney } from "../context/JourneyContext";
import { getPreferenceOption } from "../types/crowd";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";

function ArrivalPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const route = journey.selectedRoute;
  const preference = getPreferenceOption(journey.preference);

  if (!route || !journey.destination) {
    return (
      <main className="standalone-state">
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            ✓
          </span>
          <h1>No route selected</h1>
          <p>Choose a walking route to view its summary.</p>
          <Link className="button button--primary" to="/routes/search">
            Find a route
          </Link>
        </div>
      </main>
    );
  }

  function endNavigation() {
    journey.resetJourney();
    navigate(APP_CONFIG.homeRoute, { replace: true });
  }

  return (
    <main className="arrival-page">
      <section className="arrival-card">
        <div className="arrival-card__mark" aria-hidden="true">
          →
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
            <span>Selected tolerance</span>
            <strong>{preference.uiLevel}</strong>
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
