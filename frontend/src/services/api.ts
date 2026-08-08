import type { Route } from "../types/route";

const API_BASE_URL = "http://localhost:8000";

export async function fetchRoutes(
  origin: string,
  destination: string,
): Promise<Route[]> {
  const query = new URLSearchParams({ origin, destination });
  const response = await fetch(`${API_BASE_URL}/api/routes?${query.toString()}`);

  if (!response.ok) {
    throw new Error("Could not load routes. Check that the backend is running.");
  }

  return (await response.json()) as Route[];
}
