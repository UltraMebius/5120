import { Link, useNavigate } from "react-router-dom";

import { getPreferenceOption } from "../types/crowd";
import AppHeader from "../components/layout/AppHeader";
import RouteCard from "../components/route/RouteCard";
import { useJourney } from "../context/JourneyContext";
import type { WalkingRoute } from "../types/route";

function RouteOptionsPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const preference = getPreferenceOption(journey.preference);

  function handleDepart(route: WalkingRoute) {
    journey.selectRoute(route);
    navigate("/navigation");
  }

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
            <strong>Phase 1 route preview.</strong> These options are reusable
            mock data, not Mapbox routes or live crowd-ranked results. The final
            recommendation will come from CalmWay&apos;s configured crowd ranking.
          </p>
        </div>

        {journey.routes.length > 0 ? (
          <section aria-label="Walking route options" className="route-list">
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
              ↝
            </span>
            <h2>No route search yet</h2>
            <p>Enter an origin, destination and crowd tolerance first.</p>
            <Link className="button button--primary" to="/routes/search">
              Start route search
            </Link>
          </section>
        )}

        {journey.routes.length > 0 && (
          <p className="crowd-disclaimer crowd-disclaimer--footer">
            Crowd levels are relative estimates based on City of Melbourne
            pedestrian activity data. They are not medical or safety thresholds.
          </p>
        )}
      </main>
    </div>
  );
}

export default RouteOptionsPage;
