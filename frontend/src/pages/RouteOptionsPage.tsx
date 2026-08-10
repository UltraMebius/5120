import { Link, useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import RouteCard from "../components/route/RouteCard";
import { useJourney } from "../context/JourneyContext";
import { getPreferenceOption } from "../types/crowd";
import type { WalkingRoute } from "../types/route";

function RouteOptionsPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const preference = getPreferenceOption(journey.preference);

  function handleDepart(route: WalkingRoute) {
    journey.selectRoute(route);
    navigate("/navigation");
  }

  const firstRoute = journey.routes[0];

  return (
    <div className="page-frame page-frame--soft">
      <AppHeader backLabel="Edit search" backTo="/routes/search" />
      <main className="content-shell">
        <section className="page-title-row">
          <div>
            <p className="eyebrow">Route options</p>
            <h1>Choose your walk</h1>
            {journey.origin && journey.destination && (
              <p className="route-summary-line">
                <strong>{journey.origin.label}</strong>
                <span aria-hidden="true">→</span>
                <strong>{journey.destination.label}</strong>
              </p>
            )}
          </div>
          <div className="preference-summary">
            <span>Your tolerance</span>
            <strong>{preference.uiLevel}</strong>
          </div>
        </section>

        <div className="preview-notice">
          <span aria-hidden="true">i</span>
          <p>
            <strong>Real Mapbox walking routes.</strong> Distance, duration and
            route order come from Mapbox. Crowd analysis and recommendation are
            not connected yet.
          </p>
        </div>

        {journey.routes.length > 0 ? (
          <section
            aria-label="Walking route options"
            className={`route-list${
              journey.routes.length === 1 ? " route-list--single" : ""
            }`}
          >
            {journey.routes.map((route) => (
              <RouteCard
                key={route.id}
                onDepart={handleDepart}
                route={route}
              />
            ))}
          </section>
        ) : (
          <section className="empty-state">
            <span className="empty-state__icon" aria-hidden="true">
              ↗
            </span>
            <h2>No route search yet</h2>
            <p>Select an origin, destination and crowd tolerance first.</p>
            <Link className="button button--primary" to="/routes/search">
              Start route search
            </Link>
          </section>
        )}

        {import.meta.env.DEV && firstRoute && (
          <aside className="route-development-check">
            <strong>Development check — first route</strong>
            <span>
              source={firstRoute.source} · geometry={firstRoute.geometry.type} ·
              coordinates={firstRoute.geometry.coordinates.length} · distance=
              {firstRoute.distanceMeters.toFixed(1)} m · duration=
              {firstRoute.durationSeconds.toFixed(1)} s · steps=
              {firstRoute.steps.length}
            </span>
          </aside>
        )}

        {journey.routes.length > 0 && (
          <p className="crowd-disclaimer crowd-disclaimer--footer">
            Your crowd tolerance is saved, but it does not reorder routes in
            Phase 3B. Crowd analysis is coming in a later phase.
          </p>
        )}
      </main>
    </div>
  );
}

export default RouteOptionsPage;
