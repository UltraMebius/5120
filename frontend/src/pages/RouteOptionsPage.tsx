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
  const mapOrigin = journey.origin;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;
  const hasRecommendation = journey.recommendedRouteId !== null;

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
          {journey.rankingStatus === "INSUFFICIENT_DATA" ? (
            <p>
              <strong>Current crowd ranking is unavailable.</strong> These real
              Mapbox walking routes remain available, but none has enough
              current crowd coverage for a CalmWay recommendation.
            </p>
          ) : (
            <p>
              <strong>Current crowd-aware comparison.</strong> CalmWay has
              ordered these routes using the backend&apos;s provisional MVP
              crowd-ranking policy and your selected tolerance.
            </p>
          )}
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
                  isRecommended={journey.recommendedRouteId === route.id}
                  key={route.id}
                  onDepart={handleDepart}
                  onPreview={(selectedRoute) =>
                    setPreviewRouteId(selectedRoute.id)
                  }
                  route={route}
                  toleranceLevel={preference.uiLevel}
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
            {hasRecommendation
              ? "The CalmWay recommendation uses current relative pedestrian activity. The MVP ranking policy is provisional, not a medical or sensory-safety assessment."
              : "No CalmWay recommendation is shown when current crowd coverage is insufficient. Route distance, duration and geometry remain available."}
          </p>
        )}
      </main>
    </div>
  );
}

export default RouteOptionsPage;
