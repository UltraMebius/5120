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
  const [shownRouteId, setShownRouteId] = useState<string | null>(
    journey.routes[0]?.id ?? null,
  );
  const shownRoute =
    journey.routes.find((route) => route.id === shownRouteId) ??
    journey.routes[0];
  const mapOrigin = journey.origin;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;

  useEffect(() => {
    if (
      journey.routes.length > 0 &&
      !journey.routes.some((route) => route.id === shownRouteId)
    ) {
      setShownRouteId(journey.routes[0].id);
    }
  }, [journey.routes, shownRouteId]);

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

        <div className="route-notice">
          <span aria-hidden="true">i</span>
          {journey.rankingStatus === "INSUFFICIENT_DATA" ? (
            <p>
              <strong>Crowd information is currently unavailable.</strong> You
              can still view and use these walking routes.
            </p>
          ) : (
            <p>
              <strong>Routes matched to your preference.</strong> Options are
              ordered using current pedestrian activity and your selected
              crowd tolerance.
            </p>
          )}
        </div>

        {shownRoute ? (
          <div className="route-options-layout">
            <section
              aria-label="Walking route options"
              className={`route-list${
                journey.routes.length === 1 ? " route-list--single" : ""
              }`}
            >
              {journey.routes.map((route) => (
                <RouteCard
                  isShownOnMap={route.id === shownRoute.id}
                  isRecommended={journey.recommendedRouteId === route.id}
                  key={route.id}
                  onDepart={handleDepart}
                  onShowOnMap={(selectedRoute) =>
                    setShownRouteId(selectedRoute.id)
                  }
                  route={route}
                  toleranceLevel={preference.uiLevel}
                />
              ))}
            </section>
            <RouteMap
              destination={mapDestination}
              origin={mapOrigin}
              route={shownRoute}
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

        {journey.routes.length > 0 && (
          <p className="crowd-disclaimer crowd-disclaimer--footer">
            Crowd levels are relative estimates based on pedestrian activity
            data and should not be treated as medical advice or safety
            guarantees.
          </p>
        )}
      </main>
    </div>
  );
}

export default RouteOptionsPage;
