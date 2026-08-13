import type {
  GeoJsonLineString,
  JourneyLocation,
  MapboxJourneyLocation,
  WalkingRouteStep,
} from "./route";

export type ComparisonBasis = "LIVE" | "HISTORICAL_ESTIMATE" | "UNKNOWN";

export type RouteRole = "CALMEST" | "FASTEST" | "BALANCED";

export type RelativePedestrianActivity =
  | "LOWEST"
  | "MIDDLE"
  | "HIGHEST"
  | "UNKNOWN";

export type CandidateSource =
  | "DIRECT"
  | "MAPBOX_ALTERNATIVE"
  | "FLOW_WAYPOINT";

export type CandidateGenerationReason =
  | "MULTIPLE_MAPBOX_ROUTES"
  | "WAYPOINT_ALTERNATIVE_ADDED"
  | "ONLY_ONE_MEANINGFUL_CORRIDOR"
  | "NO_VALID_WAYPOINT"
  | "ALTERNATIVES_TOO_SIMILAR"
  | "DETOUR_LIMIT_EXCEEDED"
  | "JOURNEY_TOO_SHORT";

export interface PedestrianFlowEvidence {
  coveragePct: number;
  maximumMovementsPerMinute: number | null;
  medianMovementsPerMinute: number | null;
  p75MovementsPerMinute: number | null;
}

export interface ComparisonPedestrianFlow {
  basis: ComparisonBasis;
  coveragePct: number | null;
  maximumMovementsPerMinute: number | null;
  p75MovementsPerMinute: number | null;
  typicalMovementsPerMinute: number | null;
}

export interface RouteOption {
  balancedScore: number | null;
  candidateSource: CandidateSource;
  comparisonPedestrianFlow: ComparisonPedestrianFlow;
  distanceMeters: number;
  durationSeconds: number;
  geometry: GeoJsonLineString;
  historicalPedestrianFlow: PedestrianFlowEvidence;
  livePedestrianFlow: PedestrianFlowEvidence;
  relativePedestrianActivity: RelativePedestrianActivity;
  roleBadges: RouteRole[];
  routeId: string;
  routeIndex: number;
  steps: WalkingRouteStep[];
  typicalPedestrianMovementsPerMinute: number | null;
}

export interface RouteOptionsResponse {
  comparisonBasis: ComparisonBasis;
  generationReason: CandidateGenerationReason;
  routes: RouteOption[];
}

export interface RouteOptionsSearchRequest {
  destination: MapboxJourneyLocation;
  origin: JourneyLocation;
}
