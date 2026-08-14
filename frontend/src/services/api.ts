import { APP_CONFIG } from "../config";
import type {
  GeoJsonLineString,
  InitialCrowdAlert,
  RouteCrowdAlertDecision,
  RouteCrowdAlertReason,
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
import type {
  CandidateGenerationReason,
  CandidateSource,
  ComparisonBasis,
  ComparisonPedestrianFlow,
  PedestrianFlowEvidence,
  RelativePedestrianActivity,
  RouteOption,
  RouteOptionsResponse,
  RouteOptionsSearchRequest,
  RouteRole,
} from "../types/routeOptions";

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

function isNullableNonNegativeFiniteNumber(
  value: unknown,
): value is number | null {
  return value === null || isNonNegativeFiniteNumber(value);
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

function isAlertDecision(value: unknown): value is RouteCrowdAlertDecision {
  return ["ALERT", "CLEAR", "INSUFFICIENT_DATA"].includes(value as string);
}

function isAlertReason(value: unknown): value is RouteCrowdAlertReason {
  return [
    "CONSECUTIVE_ABOVE_PREFERENCE_DETECTED",
    "NO_CONSECUTIVE_ABOVE_PREFERENCE",
    "NO_USABLE_LOOK_AHEAD_CROWD_DATA",
    "NO_SAMPLES_AHEAD",
  ].includes(value as string);
}

function parseInitialCrowdAlert(value: unknown): InitialCrowdAlert | null {
  if (
    !isRecord(value) ||
    !isAlertDecision(value.decision) ||
    !isAlertReason(value.reason) ||
    !isCrowdPreference(value.preference) ||
    !isPercentage(value.threshold) ||
    value.currentProgressMeters !== 0 ||
    !isNonNegativeFiniteNumber(value.lookAheadDistanceMeters) ||
    value.lookAheadDistanceMeters === 0 ||
    !isNonNegativeInteger(value.totalLookAheadSamples) ||
    !isNonNegativeInteger(value.numericLookAheadSamples) ||
    value.numericLookAheadSamples > value.totalLookAheadSamples ||
    !isNullablePercentage(value.lookAheadCoveragePct) ||
    !isNullablePercentage(value.pctAbovePreference) ||
    !isNullableNonNegativeFiniteNumber(value.triggerStartDistanceMeters) ||
    !isNullableNonNegativeFiniteNumber(value.triggerEndDistanceMeters) ||
    !(
      value.triggerSampleCount === null ||
      (isNonNegativeInteger(value.triggerSampleCount) &&
        value.triggerSampleCount >= 2)
    ) ||
    !isNullablePercentage(value.maximumExposureInTrigger)
  ) {
    return null;
  }

  const triggerIsComplete =
    value.triggerStartDistanceMeters !== null &&
    value.triggerEndDistanceMeters !== null &&
    value.triggerStartDistanceMeters <= value.triggerEndDistanceMeters &&
    value.triggerSampleCount !== null &&
    value.maximumExposureInTrigger !== null;
  const triggerIsAbsent =
    value.triggerStartDistanceMeters === null &&
    value.triggerEndDistanceMeters === null &&
    value.triggerSampleCount === null &&
    value.maximumExposureInTrigger === null;
  const stateIsConsistent =
    (value.decision === "ALERT" &&
      value.reason === "CONSECUTIVE_ABOVE_PREFERENCE_DETECTED" &&
      value.numericLookAheadSamples >= 2 &&
      triggerIsComplete) ||
    (value.decision === "CLEAR" &&
      value.reason === "NO_CONSECUTIVE_ABOVE_PREFERENCE" &&
      value.numericLookAheadSamples > 0 &&
      triggerIsAbsent) ||
    (value.decision === "INSUFFICIENT_DATA" &&
      [
        "NO_USABLE_LOOK_AHEAD_CROWD_DATA",
        "NO_SAMPLES_AHEAD",
      ].includes(value.reason) &&
      value.numericLookAheadSamples === 0 &&
      triggerIsAbsent);
  const coverageIsConsistent =
    value.totalLookAheadSamples === 0
      ? value.lookAheadCoveragePct === null
      : value.lookAheadCoveragePct !== null &&
        Math.abs(
          value.lookAheadCoveragePct -
            (100 * value.numericLookAheadSamples) /
              value.totalLookAheadSamples,
        ) < 0.000001;
  const percentageIsConsistent =
    value.numericLookAheadSamples === 0
      ? value.pctAbovePreference === null
      : value.pctAbovePreference !== null;

  if (!stateIsConsistent || !coverageIsConsistent || !percentageIsConsistent) {
    return null;
  }

  return {
    currentProgressMeters: value.currentProgressMeters,
    decision: value.decision,
    lookAheadCoveragePct: value.lookAheadCoveragePct,
    lookAheadDistanceMeters: value.lookAheadDistanceMeters,
    maximumExposureInTrigger: value.maximumExposureInTrigger,
    numericLookAheadSamples: value.numericLookAheadSamples,
    pctAbovePreference: value.pctAbovePreference,
    preference: value.preference,
    reason: value.reason,
    threshold: value.threshold,
    totalLookAheadSamples: value.totalLookAheadSamples,
    triggerEndDistanceMeters: value.triggerEndDistanceMeters,
    triggerSampleCount: value.triggerSampleCount,
    triggerStartDistanceMeters: value.triggerStartDistanceMeters,
  };
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
  const initialCrowdAlert = parseInitialCrowdAlert(value.initialCrowdAlert);
  const steps = value.steps.map(parseStep);
  if (!geometry || !initialCrowdAlert || steps.some((step) => step === null)) {
    return null;
  }
  return {
    dataCoveragePct: value.dataCoveragePct,
    distanceMeters: value.distanceMeters,
    durationSeconds: value.durationSeconds,
    geometry,
    id: value.id,
    initialCrowdAlert,
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
    parsedRoutes.some(
      (route) => route.initialCrowdAlert.preference !== body.preference,
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

function isComparisonBasis(value: unknown): value is ComparisonBasis {
  return ["LIVE", "HISTORICAL_ESTIMATE", "UNKNOWN"].includes(
    value as string,
  );
}

function isCandidateGenerationReason(
  value: unknown,
): value is CandidateGenerationReason {
  return [
    "MULTIPLE_MAPBOX_ROUTES",
    "WAYPOINT_ALTERNATIVE_ADDED",
    "ONLY_ONE_MEANINGFUL_CORRIDOR",
    "NO_VALID_WAYPOINT",
    "ALTERNATIVES_TOO_SIMILAR",
    "DETOUR_LIMIT_EXCEEDED",
    "JOURNEY_TOO_SHORT",
  ].includes(value as string);
}

function isCandidateSource(value: unknown): value is CandidateSource {
  return ["DIRECT", "MAPBOX_ALTERNATIVE", "FLOW_WAYPOINT"].includes(
    value as string,
  );
}

function isRouteRole(value: unknown): value is RouteRole {
  return ["CALMEST", "FASTEST", "BALANCED"].includes(value as string);
}

function isRelativePedestrianActivity(
  value: unknown,
): value is RelativePedestrianActivity {
  return ["LOWEST", "MIDDLE", "HIGHEST", "UNKNOWN"].includes(
    value as string,
  );
}

function parsePedestrianFlowEvidence(
  value: unknown,
): PedestrianFlowEvidence | null {
  if (
    !isRecord(value) ||
    !isNullableNonNegativeFiniteNumber(value.medianMovementsPerMinute) ||
    !isNullableNonNegativeFiniteNumber(value.p75MovementsPerMinute) ||
    !isNullableNonNegativeFiniteNumber(value.maximumMovementsPerMinute) ||
    !isPercentage(value.coveragePct)
  ) {
    return null;
  }

  return {
    coveragePct: value.coveragePct,
    maximumMovementsPerMinute: value.maximumMovementsPerMinute,
    medianMovementsPerMinute: value.medianMovementsPerMinute,
    p75MovementsPerMinute: value.p75MovementsPerMinute,
  };
}

function parseComparisonPedestrianFlow(
  value: unknown,
): ComparisonPedestrianFlow | null {
  if (
    !isRecord(value) ||
    !isComparisonBasis(value.basis) ||
    !isNullableNonNegativeFiniteNumber(value.typicalMovementsPerMinute) ||
    !isNullableNonNegativeFiniteNumber(value.p75MovementsPerMinute) ||
    !isNullableNonNegativeFiniteNumber(value.maximumMovementsPerMinute) ||
    !isNullablePercentage(value.coveragePct)
  ) {
    return null;
  }

  return {
    basis: value.basis,
    coveragePct: value.coveragePct,
    maximumMovementsPerMinute: value.maximumMovementsPerMinute,
    p75MovementsPerMinute: value.p75MovementsPerMinute,
    typicalMovementsPerMinute: value.typicalMovementsPerMinute,
  };
}

function parseRouteOptionStep(value: unknown): WalkingRouteStep | null {
  if (
    !isRecord(value) ||
    typeof value.instruction !== "string" ||
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

function parseRouteOption(value: unknown): RouteOption | null {
  if (
    !isRecord(value) ||
    typeof value.routeId !== "string" ||
    !value.routeId.trim() ||
    !isNonNegativeInteger(value.routeIndex) ||
    !isCandidateSource(value.candidateSource) ||
    !isNonNegativeFiniteNumber(value.distanceMeters) ||
    !isNonNegativeFiniteNumber(value.durationSeconds) ||
    !Array.isArray(value.steps) ||
    !Array.isArray(value.roleBadges) ||
    !value.roleBadges.every(isRouteRole) ||
    new Set(value.roleBadges).size !== value.roleBadges.length ||
    !isRelativePedestrianActivity(value.relativePedestrianActivity) ||
    !isNullableNonNegativeFiniteNumber(
      value.typicalPedestrianMovementsPerMinute,
    ) ||
    !(
      value.balancedScore === null ||
      (typeof value.balancedScore === "number" &&
        Number.isFinite(value.balancedScore) &&
        value.balancedScore >= 0 &&
        value.balancedScore <= 1)
    )
  ) {
    return null;
  }

  const geometry = parseGeometry(value.geometry);
  const steps = value.steps.map(parseRouteOptionStep);
  const comparisonPedestrianFlow = parseComparisonPedestrianFlow(
    value.comparisonPedestrianFlow,
  );
  const livePedestrianFlow = parsePedestrianFlowEvidence(
    value.livePedestrianFlow,
  );
  const historicalPedestrianFlow = parsePedestrianFlowEvidence(
    value.historicalPedestrianFlow,
  );

  if (
    !geometry ||
    steps.some((step) => step === null) ||
    !comparisonPedestrianFlow ||
    !livePedestrianFlow ||
    !historicalPedestrianFlow ||
    value.typicalPedestrianMovementsPerMinute !==
      comparisonPedestrianFlow.typicalMovementsPerMinute
  ) {
    return null;
  }

  return {
    balancedScore: value.balancedScore,
    candidateSource: value.candidateSource,
    comparisonPedestrianFlow,
    distanceMeters: value.distanceMeters,
    durationSeconds: value.durationSeconds,
    geometry,
    historicalPedestrianFlow,
    livePedestrianFlow,
    relativePedestrianActivity: value.relativePedestrianActivity,
    roleBadges: value.roleBadges as RouteRole[],
    routeId: value.routeId,
    routeIndex: value.routeIndex,
    steps: steps as WalkingRouteStep[],
    typicalPedestrianMovementsPerMinute:
      value.typicalPedestrianMovementsPerMinute,
  };
}

export type RouteOptionsApiErrorReason =
  | "ROUTING_UNAVAILABLE"
  | "OPTIONS_UNAVAILABLE";

export class RouteOptionsApiError extends Error {
  readonly reason: RouteOptionsApiErrorReason;

  constructor(reason: RouteOptionsApiErrorReason) {
    super("Route options could not be loaded.");
    this.name = "RouteOptionsApiError";
    this.reason = reason;
  }
}

export async function fetchRouteOptions(
  request: RouteOptionsSearchRequest,
): Promise<RouteOptionsResponse> {
  const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/routes/options`, {
    body: JSON.stringify({
      destination: {
        longitude: request.destination.longitude,
        latitude: request.destination.latitude,
      },
      origin: {
        longitude: request.origin.longitude,
        latitude: request.origin.latitude,
      },
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new RouteOptionsApiError(
      response.status === 502
        ? "ROUTING_UNAVAILABLE"
        : "OPTIONS_UNAVAILABLE",
    );
  }

  let body: unknown;
  try {
    body = (await response.json()) as unknown;
  } catch {
    throw new RouteOptionsApiError("OPTIONS_UNAVAILABLE");
  }

  if (
    !isRecord(body) ||
    !isComparisonBasis(body.comparisonBasis) ||
    !isCandidateGenerationReason(body.generationReason) ||
    !Array.isArray(body.routes) ||
    body.routes.length < 1 ||
    body.routes.length > 3
  ) {
    throw new RouteOptionsApiError("OPTIONS_UNAVAILABLE");
  }

  const routes = body.routes.map(parseRouteOption);
  if (
    routes.some((route) => route === null) ||
    new Set(
      routes.map((route) => (route as RouteOption).routeId),
    ).size !== routes.length
  ) {
    throw new RouteOptionsApiError("OPTIONS_UNAVAILABLE");
  }

  const parsedRoutes = routes as RouteOption[];
  if (
    parsedRoutes.some(
      (route) => route.comparisonPedestrianFlow.basis !== body.comparisonBasis,
    )
  ) {
    throw new RouteOptionsApiError("OPTIONS_UNAVAILABLE");
  }

  return {
    comparisonBasis: body.comparisonBasis,
    generationReason: body.generationReason,
    routes: parsedRoutes,
  };
}
