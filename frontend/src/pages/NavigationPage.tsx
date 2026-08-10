import { Link, useNavigate } from "react-router-dom";

import CrowdAlertPanel from "../components/crowd/CrowdAlertPanel";
import NavigationMapPreview from "../components/map/NavigationMapPreview";
import { useJourney } from "../context/JourneyContext";
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
            ↗
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

  const nextStep = route.steps[0] ?? {
    distanceMeters: 0,
    durationSeconds: 0,
    instruction: "Continue along the selected walking route",
    maneuverLocation: null,
  };

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
        <NavigationMapPreview />

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
            <span className="crowd-pending-label">Crowd analysis pending</span>
          </div>

          <div className="progress-block">
            <div className="progress-block__labels">
              <span>Route progress</span>
              <strong>Preview</strong>
            </div>
            <div
              aria-label="Route progress is a navigation preview"
              className="progress-track"
              role="progressbar"
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={28}
            >
              <span style={{ width: "28%" }} />
            </div>
          </div>

          {journey.statusMessage && (
            <p className="navigation-message" role="status">
              {journey.statusMessage}
            </p>
          )}

          <details className="preview-controls">
            <summary>Later-phase UI previews</summary>
            <p>
              Navigation remains a placeholder. No live GPS, route drawing or
              crowd re-evaluation has occurred.
            </p>
            <div>
              <button
                className="button button--secondary"
                onClick={journey.showAlertPreview}
                type="button"
              >
                Preview future crowd alert
              </button>
              <button
                className="button button--secondary"
                onClick={() => navigate("/arrival")}
                type="button"
              >
                Preview arrival
              </button>
            </div>
          </details>
        </section>
      </main>

      {journey.alertVisible && (
        <CrowdAlertPanel
          alternativeAvailable={false}
          onContinue={journey.continueCurrentRoute}
          onStartAlternative={journey.startPreviewAlternative}
        />
      )}
    </div>
  );
}

export default NavigationPage;
