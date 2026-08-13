import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import MapboxMap from "../components/map/MapboxMap";
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
      navigate("/routes/options");
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
    <div className="page-frame page-frame--soft">
      <AppHeader />
      <main className="content-shell content-shell--search">
        <section className="search-intro">
          <p className="eyebrow">Melbourne CBD · Walking</p>
          <h1>Find a calmer way there</h1>
          <p>
            Choose where you&apos;re starting and going, then compare walking
            routes using pedestrian activity estimates.
          </p>
        </section>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        <MapboxMap />

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
