import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import RouteMap from "../components/map/RouteMap";
import { useJourney } from "../context/JourneyContext";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";

function NavigationPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const [isExiting, setIsExiting] = useState(false);
  const route = journey.selectedRoute;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;

  if ((!route || !journey.origin || !mapDestination) && !isExiting) {
    return <Navigate replace to="/routes/search" />;
  }

  if (!route || !journey.origin || !mapDestination) {
    return null;
  }

  const nextStep = route.steps.find((step) => step.instruction.trim());
  const instruction =
    nextStep?.instruction.trim() || "Continue along the selected route";

  function exitJourney() {
    setIsExiting(true);
    journey.resetJourney();
    navigate(APP_CONFIG.homeRoute, { replace: true });
  }

  return (
    <div className="navigation-page">
      <header className="navigation-header">
        <button
          aria-label="Back to route options"
          className="navigation-header__back"
          onClick={() => navigate("/routes/options")}
          type="button"
        >
          ←
        </button>
        <div>
          <span>Walking to</span>
          <strong>{mapDestination.label}</strong>
        </div>
        <span className="navigation-header__mode" aria-label="Walking route">
          Walk
        </span>
      </header>

      <main className="navigation-main">
        <RouteMap
          destination={mapDestination}
          origin={journey.origin}
          routes={[route]}
          variant="navigation"
        />

        <section className="maneuver-card" aria-label="Next walking direction">
          <div className="maneuver-card__arrow" aria-hidden="true">
            →
          </div>
          <div>
            {nextStep && <span>In {Math.round(nextStep.distanceMeters)} m</span>}
            <h1>{instruction}</h1>
          </div>
        </section>

        <section className="navigation-status">
          <div className="navigation-status__summary">
            <div>
              <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
              <span>estimated</span>
            </div>
            <div>
              <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
              <span>route distance</span>
            </div>
          </div>

          <p className="navigation-limit-note">
            Route guidance overview. Live location and turn-by-turn progress are
            not enabled.
          </p>

          <div className="navigation-overview-actions">
            <button
              className="button button--secondary"
              onClick={exitJourney}
              type="button"
            >
              Exit
            </button>
            <button
              className="button button--primary"
              onClick={() => navigate("/arrival")}
              type="button"
            >
              End route overview
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default NavigationPage;
