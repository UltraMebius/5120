import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AppHeader from "../components/layout/AppHeader";
import MapboxMap from "../components/map/MapboxMap";
import RouteSearchForm from "../components/route/RouteSearchForm";
import { useJourney } from "../context/JourneyContext";
import { findWalkingRoutes } from "../services/api";
import type { WalkingRouteSearchRequest } from "../types/route";

function RouteSearchPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(request: WalkingRouteSearchRequest) {
    setIsLoading(true);
    setError(null);

    try {
      const routes = await findWalkingRoutes(request);
      journey.setSearchResults(request, routes);
      navigate("/routes/options");
    } catch (requestError) {
      console.error("Unable to load route preview:", requestError);
      setError(
        "Unable to load preview routes. Check that the CalmWay backend is running and try again.",
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
            Compare walking routes by relative pedestrian activity and choose
            the crowd level that feels right for your journey.
          </p>
          <span className="phase-pill">Epic 1 · Phase 3A place search</span>
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
          initialPreference={journey.preference}
          isLoading={isLoading}
          onDraftLocationChange={journey.setDraftLocation}
          onSearch={handleSearch}
        />
      </main>
    </div>
  );
}

export default RouteSearchPage;
