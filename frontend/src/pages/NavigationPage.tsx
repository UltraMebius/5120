import { Link, useNavigate } from "react-router-dom";

import CrowdAlertPanel from "../components/crowd/CrowdAlertPanel";
import RouteMap from "../components/map/RouteMap";
import { useJourney } from "../context/JourneyContext";
import { getPreferenceOption } from "../types/crowd";
import { findLowerStimulationAlternative } from "../utils/findLowerStimulationAlternative";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";

function NavigationPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const route = journey.selectedRoute;

  if (!route || !journey.destination) {
    return (
      <main className="standalone-state">
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            →
          </span>
          <h1>No active journey</h1>
          <p>Choose a route before starting navigation.</p>
          <Link className="button button--primary" to="/routes/options">
            View route options
          </Link>
        </div>
      </main>
    );
  }

  const alert = route.initialCrowdAlert;
  const preference = getPreferenceOption(journey.preference);
  const alertAcknowledged = journey.acknowledgedAlertRouteIds.includes(
    route.id,
  );
  const alternative =
    alert.decision === "ALERT"
      ? findLowerStimulationAlternative(route, journey.routes)
      : null;
  const nextStep = route.steps[0] ?? {
    distanceMeters: 0,
    durationSeconds: 0,
    instruction: "Continue along the selected walking route",
    maneuverLocation: null,
  };
  const mapOrigin = journey.origin;
  const mapDestination =
    journey.destination.source === "MAPBOX" ? journey.destination : null;
  const alertLabel =
    alert.decision === "ALERT"
      ? "Crowd alert ahead"
      : alert.decision === "CLEAR"
        ? "No alert triggered"
        : "Monitoring unavailable";

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
          <strong>{journey.destination.label}</strong>
        </div>
        <span className="navigation-header__mode" aria-label="Walking route">
          Walk
        </span>
      </header>

      <main className="navigation-main">
        <RouteMap
          destination={mapDestination}
          origin={mapOrigin}
          route={route}
          variant="navigation"
        />

        <section className="maneuver-card" aria-label="Next walking direction">
          <div className="maneuver-card__arrow" aria-hidden="true">
            ↑
          </div>
          <div>
            <span>In {Math.round(nextStep.distanceMeters)} m</span>
            <h1>{nextStep.instruction}</h1>
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
            <span
              className={`navigation-crowd-label navigation-crowd-label--${alert.decision.toLowerCase()}`}
            >
              {alertLabel}
            </span>
          </div>

          <p className="navigation-preview-note">
            Initial route-ahead check at 0 m. This overview does not track live
            location or route progress.
          </p>

          {journey.statusMessage && (
            <p className="navigation-message" role="status">
              {journey.statusMessage}
            </p>
          )}

          {alert.decision === "ALERT" && !alertAcknowledged && (
            <CrowdAlertPanel
              alert={alert}
              alternative={alternative}
              onContinue={() => journey.acknowledgeCrowdAlert(route.id)}
              onStartAlternative={() => {
                if (alternative) {
                  journey.switchToAlternativeRoute(alternative);
                }
              }}
              toleranceLevel={preference.uiLevel}
            />
          )}

          {alert.decision === "CLEAR" && (
            <section
              aria-labelledby="crowd-clear-title"
              className="navigation-crowd-state navigation-crowd-state--clear"
            >
              <strong id="crowd-clear-title">No crowd alert detected ahead</strong>
              <p>
                No crowd alert is currently triggered from the available
                route-ahead data.
              </p>
            </section>
          )}

          {alert.decision === "INSUFFICIENT_DATA" && (
            <section
              aria-labelledby="crowd-unavailable-title"
              className="navigation-crowd-state navigation-crowd-state--unavailable"
              role="status"
            >
              <strong id="crowd-unavailable-title">
                Crowd monitoring unavailable
              </strong>
              <p>
                There is not enough current pedestrian data ahead to assess
                your crowd preference.
              </p>
            </section>
          )}
        </section>
      </main>
    </div>
  );
}

export default NavigationPage;
