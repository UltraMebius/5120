import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import RouteMap from "../components/map/RouteMap";
import { useJourney } from "../context/JourneyContext";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";
import {
  formatPedestrianActivity,
  pedestrianActivityLabel,
} from "../utils/routeOptionPresentation";

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
  const routeRole = route.roleBadges.join(" + ") || "Selected route";

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
          &larr;
        </button>
        <div>
          <span>Route guidance</span>
          <strong>{mapDestination.label}</strong>
        </div>
        <span className="navigation-header__mode" aria-label="Walking mode">
          Walk
        </span>
      </header>

      <main className="navigation-main">
        <RouteMap
          activeRouteId={route.routeId}
          destination={mapDestination}
          origin={journey.origin}
          routes={[route]}
          variant="navigation"
        />

        <section className="maneuver-card" aria-label="Next walking direction">
          <div className="maneuver-card__arrow" aria-hidden="true">
            &rarr;
          </div>
          <div>
            <span>Next route instruction</span>
            <h1>{instruction}</h1>
          </div>
        </section>

        <section className="navigation-status" aria-label="Route summary">
          <div className="navigation-status__summary">
            <div>
              <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
              <span>estimated time</span>
            </div>
            <div>
              <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
              <span>route distance</span>
            </div>
            <div>
              <strong>{routeRole}</strong>
              <span>selected option</span>
            </div>
            <div>
              <strong>
                {formatPedestrianActivity(
                  route.typicalPedestrianMovementsPerMinute,
                  route.comparisonPedestrianFlow.basis,
                )}
              </strong>
              <span>
                {pedestrianActivityLabel(route.relativePedestrianActivity)}
              </span>
            </div>
          </div>

          <p className="navigation-limit-note">
            Follow the backend-provided route instructions. Live position and
            turn-by-turn tracking are not enabled.
          </p>

          <div className="navigation-overview-actions">
            <button
              className="button button--secondary"
              onClick={exitJourney}
              type="button"
            >
              Exit navigation
            </button>
            <button
              className="button button--primary"
              onClick={() => navigate("/arrival")}
              type="button"
            >
              Finish route
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default NavigationPage;
