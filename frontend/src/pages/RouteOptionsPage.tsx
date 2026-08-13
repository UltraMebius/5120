import { Navigate, useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import RouteMap from "../components/map/RouteMap";
import RouteCard from "../components/route/RouteCard";
import { useJourney } from "../context/JourneyContext";
import type { RouteOption } from "../types/routeOptions";
import { pedestrianSourceLabel } from "../utils/routeOptionPresentation";

function RouteOptionsPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const response = journey.routeOptionsResponse;
  const mapDestination =
    journey.destination?.source === "MAPBOX" ? journey.destination : null;

  if (
    !response ||
    journey.routeOptions.length === 0 ||
    !journey.origin ||
    !mapDestination
  ) {
    return <Navigate replace to="/routes/search" />;
  }

  function handleSelect(route: RouteOption) {
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
            <p className="route-summary-line">
              <strong>{journey.origin.label}</strong>
              <span aria-hidden="true">→</span>
              <strong>{mapDestination.label}</strong>
            </p>
          </div>
          <div className="preference-summary">
            <span>Available</span>
            <strong>
              {journey.routeOptions.length} route
              {journey.routeOptions.length === 1 ? "" : "s"}
            </strong>
          </div>
        </section>

        <div className="route-notice">
          <span aria-hidden="true">i</span>
          <p>
            <strong>{pedestrianSourceLabel(response.comparisonBasis)}.</strong>{" "}
            Route roles and order come from the route service. Activity colours
            indicate relative pedestrian activity.
          </p>
        </div>

        <div className="route-options-layout">
          <section
            aria-label="Walking route options"
            className={`route-list${
              journey.routeOptions.length === 1 ? " route-list--single" : ""
            }`}
          >
            {journey.routeOptions.map((route, index) => (
              <RouteCard
                comparisonBasis={response.comparisonBasis}
                key={route.routeId}
                onSelect={handleSelect}
                optionNumber={index + 1}
                route={route}
              />
            ))}
          </section>
          <RouteMap
            destination={mapDestination}
            origin={journey.origin}
            routes={journey.routeOptions}
            variant="options"
          />
        </div>

        <p className="crowd-disclaimer crowd-disclaimer--footer">
          Pedestrian activity is an estimate and should not be treated as a
          medical recommendation or safety guarantee.
        </p>
      </main>
    </div>
  );
}

export default RouteOptionsPage;
