import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import RouteMap from "../components/map/RouteMap";
import RouteCard from "../components/route/RouteCard";
import { useJourney } from "../context/JourneyContext";
import type { RouteOption } from "../types/routeOptions";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../utils/formatRoute";
import {
  formatPedestrianActivity,
  pedestrianActivityLabel,
  pedestrianSourceLabel,
} from "../utils/routeOptionPresentation";

const ACTIVE_ROUTE_PANEL_ID = "active-route-details";

function routeLabel(route: RouteOption, index: number): string {
  return route.roleBadges.length > 0
    ? route.roleBadges.join(" + ")
    : `Route ${index + 1}`;
}

function RouteOptionsPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const response = journey.routeOptionsResponse;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;
  const [activeRouteId, setActiveRouteId] = useState(
    journey.selectedRoute?.routeId ?? journey.routeOptions[0]?.routeId ?? "",
  );

  if (
    !response ||
    journey.routeOptions.length === 0 ||
    !journey.origin ||
    !mapDestination
  ) {
    return <Navigate replace to="/routes/search" />;
  }

  const activeRoute =
    journey.routeOptions.find((route) => route.routeId === activeRouteId) ??
    journey.routeOptions[0];
  const activeIndex = journey.routeOptions.findIndex(
    (route) => route.routeId === activeRoute.routeId,
  );
  const activeLabel = routeLabel(activeRoute, activeIndex);

  function handleSelect(route: RouteOption) {
    journey.selectRoute(route);
    navigate("/navigation");
  }

  return (
    <div className="page-frame page-frame--soft route-options-page">
      <AppHeader backLabel="Edit search" backTo="/routes/search" />
      <main className="content-shell route-options-shell">
        <header className="route-options-heading">
          <div>
            <p className="eyebrow">Route options</p>
            <h1>Choose your walk</h1>
          </div>
          <p className="route-summary-line">
            <strong>{journey.origin.label}</strong>
            <span aria-hidden="true">&rarr;</span>
            <strong>{mapDestination.label}</strong>
          </p>
          <div className="route-data-status">
            <span>{pedestrianSourceLabel(response.comparisonBasis)}</span>
            <details className="metric-info">
              <summary aria-label="About movements per minute">i</summary>
              <p>
                Estimated pedestrian movements per minute along the route,
                based on nearby sensors.
              </p>
            </details>
          </div>
        </header>

        <div className="route-options-layout">
          <section className="route-choice-panel" aria-label="Walking route options">
            <div
              aria-label="Choose a route to review"
              className={`route-list route-list--count-${journey.routeOptions.length}`}
              role="tablist"
            >
              {journey.routeOptions.map((route, index) => (
                <RouteCard
                  comparisonBasis={response.comparisonBasis}
                  isSelected={route.routeId === activeRoute.routeId}
                  key={route.routeId}
                  onActivate={() => setActiveRouteId(route.routeId)}
                  optionNumber={index + 1}
                  panelId={ACTIVE_ROUTE_PANEL_ID}
                  route={route}
                />
              ))}
            </div>

            <section
              aria-labelledby={`route-tab-${activeRoute.routeId}`}
              className="active-route-detail"
              id={ACTIVE_ROUTE_PANEL_ID}
              role="tabpanel"
            >
              <div className="active-route-detail__summary">
                <div>
                  <span>Selected option</span>
                  <strong>{activeLabel}</strong>
                </div>
                <div>
                  <span>Typical activity</span>
                  <strong>
                    {formatPedestrianActivity(
                      activeRoute.typicalPedestrianMovementsPerMinute,
                      response.comparisonBasis,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Walk</span>
                  <strong>
                    {formatWalkingDuration(activeRoute.durationSeconds)} ·{" "}
                    {formatWalkingDistance(activeRoute.distanceMeters)}
                  </strong>
                </div>
              </div>
              <p className="active-route-detail__activity">
                {pedestrianActivityLabel(
                  activeRoute.relativePedestrianActivity,
                )}
                <span aria-hidden="true"> · </span>
                {pedestrianSourceLabel(response.comparisonBasis)}
              </p>
              <button
                aria-label={`Select ${activeLabel} route`}
                className="button button--primary button--full"
                onClick={() => handleSelect(activeRoute)}
                type="button"
              >
                Select route
                <span aria-hidden="true">&rarr;</span>
              </button>
            </section>

            <p className="route-choice-disclaimer">
              Estimates describe relative route activity, not an exact number
              of people at every point.
            </p>
          </section>

          <RouteMap
            activeRouteId={activeRoute.routeId}
            destination={mapDestination}
            origin={journey.origin}
            routes={journey.routeOptions}
            variant="options"
          />
        </div>
      </main>
    </div>
  );
}

export default RouteOptionsPage;
