import { useState } from "react";

import RouteCard from "./components/RouteCard";
import RouteSearchForm from "./components/RouteSearchForm";
import { fetchRoutes } from "./services/api";
import type { Route } from "./types/route";

function App() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  async function handleSearch(origin: string, destination: string) {
    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const routeOptions = await fetchRoutes(origin, destination);
      setRoutes(routeOptions);
    } catch (requestError) {
      console.error("Unable to load routes:", requestError);
      setRoutes([]);
      setError("Unable to load routes. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Melbourne CBD practice prototype</p>
        <h1>CalmWay</h1>
        <p className="subtitle">
          Compare simple sensory indicators for walking route options.
        </p>
      </header>

      <RouteSearchForm onSearch={handleSearch} isLoading={isLoading} />

      <section className="results" aria-live="polite" aria-busy={isLoading}>
        {isLoading && <p>Finding mock route options...</p>}
        {error && <p className="error-message">{error}</p>}

        {!isLoading && !error && routes.length > 0 && (
          <>
            <div className="results-heading">
              <h2>Route options</h2>
              <p>Temporary mock results for this practice iteration.</p>
            </div>
            <div className="route-list">
              {routes.map((route) => (
                <RouteCard key={route.id} route={route} />
              ))}
            </div>
          </>
        )}

        {!isLoading && !error && hasSearched && routes.length === 0 && (
          <p>No route options are available.</p>
        )}
      </section>
    </main>
  );
}

export default App;
