import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import RouteMap from "../components/map/RouteMap";
import RouteCard from "../components/route/RouteCard";
import { APP_CONFIG } from "../config";
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
const MODE_TRANSITION_DURATION_MS = 700;

type NavigationUiMode =
  | "active"
  | "selection"
  | "transition-to-active"
  | "transition-to-selection";

function routeLabel(route: RouteOption, index: number): string {
  return route.roleBadges.length > 0
    ? route.roleBadges.join(" + ")
    : `Route ${index + 1}`;
}

function NavigationPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const transitionTimerRef = useRef<number | null>(null);
  const [isExiting, setIsExiting] = useState(false);
  const [uiMode, setUiMode] = useState<NavigationUiMode>(
    journey.selectedRoute ? "active" : "selection",
  );
  const [activeRouteId, setActiveRouteId] = useState(
    journey.selectedRoute?.routeId ?? journey.routeOptions[0]?.routeId ?? "",
  );
  const route = journey.selectedRoute;
  const response = journey.routeOptionsResponse;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;

  useEffect(
    () => () => {
      if (transitionTimerRef.current !== null) {
        window.clearTimeout(transitionTimerRef.current);
      }
    },
    [],
  );

  if (
    (!response ||
      journey.routeOptions.length === 0 ||
      !journey.origin ||
      !mapDestination) &&
    !isExiting
  ) {
    return <Navigate replace to="/routes/search" />;
  }

  if (!response || !journey.origin || !mapDestination) {
    return null;
  }

  const activeRoute =
    journey.routeOptions.find(
      (candidate) => candidate.routeId === activeRouteId,
    ) ?? journey.routeOptions[0];
  const activeIndex = journey.routeOptions.findIndex(
    (candidate) => candidate.routeId === activeRoute.routeId,
  );
  const activeLabel = routeLabel(activeRoute, activeIndex);
  const displayedRoute = route ?? activeRoute;
  const displayedRouteRole =
    displayedRoute.roleBadges.join(" + ") || "Selected route";
  const nextStep = displayedRoute.steps.find((step) =>
    step.instruction.trim(),
  );
  const instruction =
    nextStep?.instruction.trim() || "Continue along the selected route";
  const selectionInteractive = uiMode === "selection";
  const activeInteractive = uiMode === "active";
  const mapMode =
    uiMode === "selection" || uiMode === "transition-to-selection"
      ? "selection"
      : "active";

  function finishTransition(nextMode: NavigationUiMode) {
    if (transitionTimerRef.current !== null) {
      window.clearTimeout(transitionTimerRef.current);
    }
    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    transitionTimerRef.current = window.setTimeout(() => {
      setUiMode(nextMode);
      transitionTimerRef.current = null;
    }, reduceMotion ? 0 : MODE_TRANSITION_DURATION_MS);
  }

  function confirmRoute() {
    if (!selectionInteractive) {
      return;
    }
    journey.selectRoute(activeRoute);
    setUiMode("transition-to-active");
    finishTransition("active");
  }

  function returnToSelection() {
    if (!activeInteractive) {
      return;
    }
    setUiMode("transition-to-selection");
    journey.returnToRouteSelection();
    finishTransition("selection");
  }

  function exitJourney() {
    setIsExiting(true);
    journey.resetJourney();
    navigate(APP_CONFIG.homeRoute, { replace: true });
  }

  return (
    <div
      className={`navigation-page navigation-page--continuous navigation-page--${uiMode}`}
      data-navigation-mode={uiMode}
      data-testid="navigation-page"
    >
      <main className="navigation-main">
        <RouteMap
          activeRouteId={displayedRoute.routeId}
          destination={mapDestination}
          mode={mapMode}
          origin={journey.origin}
          routes={journey.routeOptions}
        />

        <section
          aria-hidden={!selectionInteractive}
          aria-labelledby="route-selection-heading"
          className="route-choice-panel navigation-route-panel"
          data-testid="route-selection-panel"
          {...(!selectionInteractive ? { inert: "" } : {})}
        >
          <header className="navigation-route-panel__header">
            <div className="navigation-route-panel__topline">
              <button
                className="navigation-edit-search"
                onClick={() => navigate("/routes/search")}
                type="button"
              >
                <span aria-hidden="true">&larr;</span> Edit search
              </button>
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
            </div>
            <p className="eyebrow">Route options</p>
            <h1 id="route-selection-heading">Choose your walk</h1>
            <p className="route-summary-line">
              <strong>{journey.origin.label}</strong>
              <span aria-hidden="true">&rarr;</span>
              <strong>{mapDestination.label}</strong>
            </p>
          </header>

          <div
            aria-label="Choose a route to review"
            className={`route-list route-list--count-${journey.routeOptions.length}`}
            role="tablist"
          >
            {journey.routeOptions.map((candidate, index) => (
              <RouteCard
                comparisonBasis={response.comparisonBasis}
                isSelected={candidate.routeId === activeRoute.routeId}
                key={candidate.routeId}
                onActivate={() => setActiveRouteId(candidate.routeId)}
                optionNumber={index + 1}
                panelId={ACTIVE_ROUTE_PANEL_ID}
                route={candidate}
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
                  {formatWalkingDuration(activeRoute.durationSeconds)} {" · "}
                  {formatWalkingDistance(activeRoute.distanceMeters)}
                </strong>
              </div>
            </div>
            <p className="active-route-detail__activity">
              {pedestrianActivityLabel(activeRoute.relativePedestrianActivity)}
              <span aria-hidden="true"> · </span>
              {pedestrianSourceLabel(response.comparisonBasis)}
            </p>
            <button
              aria-label={`Select ${activeLabel} route`}
              className="button button--primary button--full"
              onClick={confirmRoute}
              type="button"
            >
              Select route
              <span aria-hidden="true">&rarr;</span>
            </button>
          </section>

          <p className="route-choice-disclaimer">
            Estimates describe relative route activity, not an exact number of
            people at every point.
          </p>
        </section>

        <header
          aria-hidden={!activeInteractive}
          className="navigation-header navigation-active-overlay"
          data-testid="navigation-guidance-header"
          {...(!activeInteractive ? { inert: "" } : {})}
        >
          <button
            aria-label="Back to route selection"
            className="navigation-header__back"
            onClick={returnToSelection}
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

        <section
          aria-hidden={!activeInteractive}
          aria-label="Next walking direction"
          className="maneuver-card navigation-active-overlay"
          {...(!activeInteractive ? { inert: "" } : {})}
        >
          <div className="maneuver-card__arrow" aria-hidden="true">
            &rarr;
          </div>
          <div>
            <span>Next route instruction</span>
            <h1>{instruction}</h1>
          </div>
        </section>

        <section
          aria-hidden={!activeInteractive}
          aria-label="Route summary"
          className="navigation-status navigation-active-overlay"
          {...(!activeInteractive ? { inert: "" } : {})}
        >
          <div className="navigation-status__summary">
            <div>
              <strong>
                {formatWalkingDuration(displayedRoute.durationSeconds)}
              </strong>
              <span>estimated time</span>
            </div>
            <div>
              <strong>
                {formatWalkingDistance(displayedRoute.distanceMeters)}
              </strong>
              <span>route distance</span>
            </div>
            <div>
              <strong>{displayedRouteRole}</strong>
              <span>selected option</span>
            </div>
            <div>
              <strong>
                {formatPedestrianActivity(
                  displayedRoute.typicalPedestrianMovementsPerMinute,
                  displayedRoute.comparisonPedestrianFlow.basis,
                )}
              </strong>
              <span>
                {pedestrianActivityLabel(
                  displayedRoute.relativePedestrianActivity,
                )}
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
