import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import RouteSearchForm from "../components/route/RouteSearchForm";
import { useJourney } from "../context/JourneyContext";
import { fetchRouteOptions, RouteOptionsApiError } from "../services/api";
import type { RouteOptionsSearchRequest } from "../types/routeOptions";

function RouteSearchPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(request: RouteOptionsSearchRequest) {
    setIsLoading(true);
    setError(null);

    try {
      const result = await fetchRouteOptions(request);
      journey.setRouteOptions(request, result);
      navigate("/navigation");
    } catch (requestError: unknown) {
      console.error("Unable to load route options.");
      setError(
        requestError instanceof RouteOptionsApiError &&
          requestError.reason === "ROUTING_UNAVAILABLE"
          ? "Walking routes are currently unavailable. Please try again."
          : "Unable to load route options right now. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="page-frame page-frame--soft route-search-page">
      <AppHeader />
      <main className="content-shell content-shell--search search-shell">
        <section className="search-intro">
          <p className="eyebrow">Plan your walk</p>
          <h1>Find a calmer way there</h1>
          <p>
            Choose a starting point and destination to compare walking routes.
          </p>
        </section>

        {error && (
          <p className="error-message" role="alert">
            We couldn&apos;t find walking routes for those locations. Please try
            again.
          </p>
        )}

        {isLoading && (
          <div className="route-loading-status" role="status">
            <span className="route-loading-status__spinner" aria-hidden="true" />
            <span>
              <strong>Finding walking routes...</strong>
              <small>Comparing available walking options</small>
            </span>
          </div>
        )}

        <RouteSearchForm
          initialDestination={journey.destination}
          initialOrigin={journey.origin}
          isLoading={isLoading}
          onDraftLocationChange={journey.setDraftLocation}
          onSearch={handleSearch}
        />
      </main>
    </div>
  );
}

export default RouteSearchPage;
