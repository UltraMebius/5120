import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import RouteMap from "../components/map/RouteMap";
import RouteCard from "../components/route/RouteCard";
import { useJourney } from "../context/JourneyContext";
import { getPreferenceOption } from "../types/crowd";
import type { WalkingRoute } from "../types/route";

function RouteOptionsPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const preference = getPreferenceOption(journey.preference);
  const [previewRouteId, setPreviewRouteId] = useState<string | null>(
    journey.routes[0]?.id ?? null,
  );
  const previewRoute =
    journey.routes.find((route) => route.id === previewRouteId) ??
    journey.routes[0];
  const mapOrigin =
    journey.origin?.source === "MAPBOX" ? journey.origin : null;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;

  useEffect(() => {
    if (
      journey.routes.length > 0 &&
      !journey.routes.some((route) => route.id === previewRouteId)
    ) {
      setPreviewRouteId(journey.routes[0].id);
    }
  }, [journey.routes, previewRouteId]);

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
            <strong>Real Mapbox walking routes.</strong> Distance, duration and
            route order come from Mapbox. Crowd analysis and recommendation are
            not connected yet.
          </p>
        </div>

        {previewRoute ? (
          <div className="route-options-layout">
            <section
              aria-label="Walking route options"
              className={`route-list${
                journey.routes.length === 1 ? " route-list--single" : ""
              }`}
            >
              {journey.routes.map((route) => (
                <RouteCard
                  isPreviewed={route.id === previewRoute.id}
                  key={route.id}
                  onDepart={handleDepart}
                  onPreview={(selectedRoute) =>
                    setPreviewRouteId(selectedRoute.id)
                  }
                  route={route}
                />
              ))}
            </section>
            <RouteMap
              destination={mapDestination}
              origin={mapOrigin}
              route={previewRoute}
              variant="options"
            />
          </div>
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

        {import.meta.env.DEV && previewRoute && (
          <aside className="route-development-check">
            <strong>Development check — previewed route</strong>
            <span>
              source={previewRoute.source} · geometry=
              {previewRoute.geometry.type} · coordinates=
              {previewRoute.geometry.coordinates.length} · distance=
              {previewRoute.distanceMeters.toFixed(1)} m · duration=
              {previewRoute.durationSeconds.toFixed(1)} s · steps=
              {previewRoute.steps.length}
            </span>
          </aside>
        )}

        {journey.routes.length > 0 && (
          <p className="crowd-disclaimer crowd-disclaimer--footer">
            Your crowd tolerance is saved, but it does not reorder routes in
            this phase. Crowd analysis is coming in a later phase.
          </p>
        )}
      </main>
    </div>
  );
}

export default RouteOptionsPage;
