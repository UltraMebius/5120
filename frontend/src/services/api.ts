import { APP_CONFIG } from "../config";
import type {
  WalkingRoute,
  WalkingRouteSearchRequest,
} from "../types/route";

export async function findWalkingRoutes(
  request: WalkingRouteSearchRequest,
): Promise<WalkingRoute[]> {
  const query = new URLSearchParams({
    origin: request.origin.label,
    destination: request.destination.label,
    preference: request.preference,
  });
  const response = await fetch(
    `${APP_CONFIG.apiBaseUrl}/api/routes?${query.toString()}`,
  );

  if (!response.ok) {
    throw new Error("Could not load routes. Check that the backend is running.");
  }

  return (await response.json()) as WalkingRoute[];
}
