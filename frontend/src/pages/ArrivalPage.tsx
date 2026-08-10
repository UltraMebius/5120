import { Link, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import { useJourney } from "../context/JourneyContext";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";

function ArrivalPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const route = journey.selectedRoute;

  if (!route || !journey.destination) {
    return (
      <main className="standalone-state">
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            ✓
          </span>
          <h1>No completed journey</h1>
          <p>Start a route to preview the arrival summary.</p>
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
          ✓
        </div>
        <p className="eyebrow">Journey complete</p>
        <h1>You&apos;ve arrived</h1>
        <p className="arrival-card__destination">
          {journey.destination.label}
        </p>

        <div className="arrival-stats">
          <div>
            <span>Estimated time</span>
            <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
          </div>
          <div>
            <span>Route distance</span>
            <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
          </div>
          <div>
            <span>Journey crowd load</span>
            <strong>Not evaluated</strong>
          </div>
        </div>

        <p className="preview-caption">
          Navigation remains a preview; the route summary uses real Mapbox
          distance and duration.
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
