import { Link, useNavigate } from "react-router-dom";

import CrowdAlertPanel from "../components/crowd/CrowdAlertPanel";
import CrowdBadge from "../components/crowd/CrowdBadge";
import NavigationMapPreview from "../components/map/NavigationMapPreview";
import { useJourney } from "../context/JourneyContext";

const CROWD_ORDER = { LOW: 0, MEDIUM: 1, HIGH: 2 } as const;

function NavigationPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const route = journey.selectedRoute;

  if (!route || !journey.destination) {
    return (
      <main className="standalone-state">
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            ↑
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

  const nextManeuver = route.maneuvers?.[0] ?? {
    direction: "LEFT" as const,
    distanceM: 120,
    instruction: "Turn left onto Swanston Street",
  };
  const alternativeAvailable = journey.routes.some(
    (candidate) =>
      candidate.id !== route.id &&
      CROWD_ORDER[candidate.crowdLevel] < CROWD_ORDER[route.crowdLevel],
  );

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
          ♙
        </span>
      </header>

      <main className="navigation-main">
        <NavigationMapPreview />

        <section className="maneuver-card" aria-label="Next walking direction">
          <div className="maneuver-card__arrow" aria-hidden="true">
            {nextManeuver.direction === "LEFT"
              ? "↰"
              : nextManeuver.direction === "RIGHT"
                ? "↱"
                : "↑"}
          </div>
          <div>
            <span>In {nextManeuver.distanceM} m</span>
            <h1>{nextManeuver.instruction}</h1>
          </div>
        </section>

        <section className="navigation-status">
          <div className="navigation-status__summary">
            <div>
              <strong>{route.durationMin} min</strong>
              <span>remaining</span>
            </div>
            <div>
              <strong>{route.distanceKm.toFixed(1)} km</strong>
              <span>remaining</span>
            </div>
            <CrowdBadge level={route.crowdLevel} />
          </div>

          <div className="progress-block">
            <div className="progress-block__labels">
              <span>Route progress</span>
              <strong>Preview</strong>
            </div>
            <div
              aria-label="Route progress is a Phase 1 preview"
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
            <summary>Phase 1 state previews</summary>
            <p>
              These controls demonstrate the alert and arrival screens without
              claiming live GPS or crowd re-evaluation.
            </p>
            <div>
              <button
                className="button button--secondary"
                onClick={journey.showAlertPreview}
                type="button"
              >
                Preview crowd alert
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
          alternativeAvailable={alternativeAvailable}
          onContinue={journey.continueCurrentRoute}
          onStartAlternative={journey.startPreviewAlternative}
        />
      )}
    </div>
  );
}

export default NavigationPage;
