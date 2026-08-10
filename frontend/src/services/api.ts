import { APP_CONFIG } from "../config";
import type {
  GeoJsonLineString,
  RoutePreferenceStatus,
  RouteRankingStatus,
  WalkingRoute,
  WalkingRouteSearchRequest,
  WalkingRouteStep,
  WalkingRoutesResult,
} from "../types/route";
import type {
  CrowdPreference,
  FrontendCrowdLevel,
  InternalCrowdLevel,
} from "../types/crowd";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonNegativeFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isPercentage(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 100
  );
}

function isNullablePercentage(value: unknown): value is number | null {
  return value === null || isPercentage(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0;
}

function isInternalCrowdLevel(value: unknown): value is InternalCrowdLevel {
  return ["VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"].includes(
    value as string,
  );
}

function isFrontendCrowdLevel(value: unknown): value is FrontendCrowdLevel {
  return ["LOW", "MEDIUM", "HIGH"].includes(value as string);
}

function isCrowdPreference(value: unknown): value is CrowdPreference {
  return ["AVOID_BUSY", "PREFER_QUIETER", "FLEXIBLE"].includes(
    value as string,
  );
}

function isPreferenceStatus(value: unknown): value is RoutePreferenceStatus {
  return [
    "WITHIN_PREFERENCE",
    "ABOVE_PREFERENCE",
    "INSUFFICIENT_DATA",
  ].includes(value as string);
}

function isRankingStatus(value: unknown): value is RouteRankingStatus {
  return [
    "NOT_EVALUATED",
    "PROVISIONAL",
    "INSUFFICIENT_DATA",
    "VALIDATED",
  ].includes(value as string);
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
    !Array.isArray(value.steps) ||
    !isPercentage(value.supportedPct) ||
    !isPercentage(value.limitedCoveragePct) ||
    !isPercentage(value.dataCoveragePct) ||
    !isPercentage(value.noDataPct) ||
    !isNullablePercentage(value.medianCrowdExposureScore) ||
    !isNullablePercentage(value.p75CrowdExposureScore) ||
    !isNullablePercentage(value.maximumCrowdExposureScore) ||
    !isNullablePercentage(value.pctAbovePreference) ||
    !isNullablePercentage(value.pctVeryHigh) ||
    !isNonNegativeFiniteNumber(value.sampleIntervalM) ||
    value.sampleIntervalM === 0 ||
    !isNonNegativeInteger(value.sampleCount) ||
    !isNonNegativeInteger(value.numericSampleCount) ||
    !isPreferenceStatus(value.preferenceStatus) ||
    typeof value.isRecommended !== "boolean" ||
    !(
      value.rank === null ||
      (Number.isInteger(value.rank) &&
        typeof value.rank === "number" &&
        value.rank >= 1)
    ) ||
    !(
      value.routeCrowdLevel === null ||
      isInternalCrowdLevel(value.routeCrowdLevel)
    ) ||
    !(
      value.routeCrowdPresentationLevel === null ||
      isFrontendCrowdLevel(value.routeCrowdPresentationLevel)
    )
  ) {
    return null;
  }
  const geometry = parseGeometry(value.geometry);
  const steps = value.steps.map(parseStep);
  if (!geometry || steps.some((step) => step === null)) {
    return null;
  }
  return {
    dataCoveragePct: value.dataCoveragePct,
    distanceMeters: value.distanceMeters,
    durationSeconds: value.durationSeconds,
    geometry,
    id: value.id,
    isRecommended: value.isRecommended,
    limitedCoveragePct: value.limitedCoveragePct,
    maximumCrowdExposureScore: value.maximumCrowdExposureScore,
    medianCrowdExposureScore: value.medianCrowdExposureScore,
    name: value.name,
    noDataPct: value.noDataPct,
    numericSampleCount: value.numericSampleCount,
    p75CrowdExposureScore: value.p75CrowdExposureScore,
    pctAbovePreference: value.pctAbovePreference,
    pctVeryHigh: value.pctVeryHigh,
    preferenceStatus: value.preferenceStatus,
    rank: value.rank,
    routeCrowdLevel: value.routeCrowdLevel,
    routeCrowdPresentationLevel: value.routeCrowdPresentationLevel,
    routeIndex: value.routeIndex,
    sampleCount: value.sampleCount,
    sampleIntervalM: value.sampleIntervalM,
    source: "MAPBOX",
    steps: steps as WalkingRouteStep[],
    supportedPct: value.supportedPct,
  };
}

export async function findWalkingRoutes(
  request: WalkingRouteSearchRequest,
): Promise<WalkingRoutesResult> {
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
  if (
    !isRecord(body) ||
    !Array.isArray(body.routes) ||
    !body.routes.length ||
    !isCrowdPreference(body.preference) ||
    body.preference !== request.preference ||
    !isRankingStatus(body.rankingStatus) ||
    !(
      body.recommendedRouteId === null ||
      (typeof body.recommendedRouteId === "string" &&
        body.recommendedRouteId.length > 0)
    )
  ) {
    throw new Error("Walking routes could not be loaded.");
  }
  const routes = body.routes.map(parseRoute);
  if (routes.some((route) => route === null)) {
    throw new Error("Walking routes could not be loaded.");
  }
  const parsedRoutes = routes as WalkingRoute[];
  const recommendedRouteId = body.recommendedRouteId;
  if (
    (recommendedRouteId !== null &&
      !parsedRoutes.some((route) => route.id === recommendedRouteId)) ||
    parsedRoutes.some(
      (route) => route.isRecommended !== (route.id === recommendedRouteId),
    ) ||
    (body.rankingStatus === "PROVISIONAL" && recommendedRouteId === null) ||
    (body.rankingStatus === "INSUFFICIENT_DATA" &&
      recommendedRouteId !== null)
  ) {
    throw new Error("Walking routes could not be loaded.");
  }
  return {
    preference: body.preference,
    rankingStatus: body.rankingStatus,
    recommendedRouteId,
    routes: parsedRoutes,
  };
}
