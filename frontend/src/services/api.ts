import { APP_CONFIG } from "../config";
import type {
  GeoJsonLineString,
  WalkingRoute,
  WalkingRouteSearchRequest,
  WalkingRouteStep,
} from "../types/route";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonNegativeFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function parseCoordinatePair(
  value: unknown,
): [longitude: number, latitude: number] | null {
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }
  const [longitude, latitude] = value;
  if (
    typeof longitude !== "number" ||
    !Number.isFinite(longitude) ||
    longitude < -180 ||
    longitude > 180 ||
    typeof latitude !== "number" ||
    !Number.isFinite(latitude) ||
    latitude < -90 ||
    latitude > 90
  ) {
    return null;
  }
  return [longitude, latitude];
}

function parseGeometry(value: unknown): GeoJsonLineString | null {
  if (!isRecord(value) || value.type !== "LineString") {
    return null;
  }
  const rawCoordinates = value.coordinates;
  if (!Array.isArray(rawCoordinates) || rawCoordinates.length < 2) {
    return null;
  }
  const coordinates = rawCoordinates.map(parseCoordinatePair);
  if (coordinates.some((coordinate) => coordinate === null)) {
    return null;
  }
  return {
    type: "LineString",
    coordinates: coordinates as [number, number][],
  };
}

function parseStep(value: unknown): WalkingRouteStep | null {
  if (
    !isRecord(value) ||
    typeof value.instruction !== "string" ||
    !value.instruction.trim() ||
    !isNonNegativeFiniteNumber(value.distanceMeters) ||
    !isNonNegativeFiniteNumber(value.durationSeconds)
  ) {
    return null;
  }
  const maneuverLocation =
    value.maneuverLocation === null
      ? null
      : parseCoordinatePair(value.maneuverLocation);
  if (value.maneuverLocation !== null && maneuverLocation === null) {
    return null;
  }
  return {
    distanceMeters: value.distanceMeters,
    durationSeconds: value.durationSeconds,
    instruction: value.instruction,
    maneuverLocation,
  };
}

function parseRoute(value: unknown): WalkingRoute | null {
  if (
    !isRecord(value) ||
    value.source !== "MAPBOX" ||
    typeof value.id !== "string" ||
    !value.id ||
    typeof value.name !== "string" ||
    !value.name ||
    typeof value.routeIndex !== "number" ||
    !Number.isInteger(value.routeIndex) ||
    value.routeIndex < 0 ||
    !isNonNegativeFiniteNumber(value.distanceMeters) ||
    !isNonNegativeFiniteNumber(value.durationSeconds) ||
    !Array.isArray(value.steps)
  ) {
    return null;
  }
  const geometry = parseGeometry(value.geometry);
  const steps = value.steps.map(parseStep);
  if (!geometry || steps.some((step) => step === null)) {
    return null;
  }
  return {
    distanceMeters: value.distanceMeters,
    durationSeconds: value.durationSeconds,
    geometry,
    id: value.id,
    name: value.name,
    routeIndex: value.routeIndex,
    source: "MAPBOX",
    steps: steps as WalkingRouteStep[],
  };
}

export async function findWalkingRoutes(
  request: WalkingRouteSearchRequest,
): Promise<WalkingRoute[]> {
  const response = await fetch(
    `${APP_CONFIG.apiBaseUrl}/api/v1/routes/walking`,
    {
      body: JSON.stringify({
        destination: {
          label: request.destination.label,
          latitude: request.destination.latitude,
          longitude: request.destination.longitude,
        },
        origin: {
          label: request.origin.label,
          latitude: request.origin.latitude,
          longitude: request.origin.longitude,
        },
        preference: request.preference,
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error("Walking routes could not be loaded.");
  }

  let body: unknown;
  try {
    body = (await response.json()) as unknown;
  } catch {
    throw new Error("Walking routes could not be loaded.");
  }
  if (!isRecord(body) || !Array.isArray(body.routes) || !body.routes.length) {
    throw new Error("Walking routes could not be loaded.");
  }
  const routes = body.routes.map(parseRoute);
  if (routes.some((route) => route === null)) {
    throw new Error("Walking routes could not be loaded.");
  }
  return routes as WalkingRoute[];
}
