import type {
  CrowdPreference,
  FrontendCrowdLevel,
  InternalCrowdLevel,
} from "./crowd";

export type RoutePreferenceStatus =
  | "WITHIN_PREFERENCE"
  | "ABOVE_PREFERENCE"
  | "INSUFFICIENT_DATA";

export type RouteRankingStatus =
  | "NOT_EVALUATED"
  | "PROVISIONAL"
  | "INSUFFICIENT_DATA"
  | "VALIDATED";

export type RouteCrowdAlertDecision =
  | "ALERT"
  | "CLEAR"
  | "INSUFFICIENT_DATA";

export type RouteCrowdAlertReason =
  | "CONSECUTIVE_ABOVE_PREFERENCE_DETECTED"
  | "NO_CONSECUTIVE_ABOVE_PREFERENCE"
  | "NO_USABLE_LOOK_AHEAD_CROWD_DATA"
  | "NO_SAMPLES_AHEAD";

export interface InitialCrowdAlert {
  currentProgressMeters: number;
  decision: RouteCrowdAlertDecision;
  lookAheadCoveragePct: number | null;
  lookAheadDistanceMeters: number;
  maximumExposureInTrigger: number | null;
  numericLookAheadSamples: number;
  pctAbovePreference: number | null;
  preference: CrowdPreference;
  reason: RouteCrowdAlertReason;
  threshold: number;
  totalLookAheadSamples: number;
  triggerEndDistanceMeters: number | null;
  triggerSampleCount: number | null;
  triggerStartDistanceMeters: number | null;
}

export interface Coordinate {
  latitude: number;
  longitude: number;
}

export interface MapboxSelectedLocation {
  fullAddress: string;
  latitude: number;
  longitude: number;
  mapboxId: string;
  name: string;
}

export interface MapboxJourneyLocation extends MapboxSelectedLocation {
  label: string;
  source: "MAPBOX";
}

export interface GeolocationJourneyLocation extends Coordinate {
  label: "Current location";
  name: "Current location";
  source: "GEOLOCATION";
}

export type JourneyLocation =
  | GeolocationJourneyLocation
  | MapboxJourneyLocation;

export interface GeoJsonLineString {
  coordinates: [longitude: number, latitude: number][];
  type: "LineString";
}

export interface WalkingRouteStep {
  distanceMeters: number;
  durationSeconds: number;
  instruction: string;
  maneuverLocation: [longitude: number, latitude: number] | null;
}

export interface WalkingRoute {
  dataCoveragePct: number;
  distanceMeters: number;
  durationSeconds: number;
  geometry: GeoJsonLineString;
  id: string;
  initialCrowdAlert: InitialCrowdAlert;
  isRecommended: boolean;
  limitedCoveragePct: number;
  maximumCrowdExposureScore: number | null;
  medianCrowdExposureScore: number | null;
  name: string;
  noDataPct: number;
  numericSampleCount: number;
  p75CrowdExposureScore: number | null;
  pctAbovePreference: number | null;
  pctVeryHigh: number | null;
  preferenceStatus: RoutePreferenceStatus;
  rank: number | null;
  routeCrowdLevel: InternalCrowdLevel | null;
  routeCrowdPresentationLevel: FrontendCrowdLevel | null;
  routeIndex: number;
  sampleCount: number;
  sampleIntervalM: number;
  source: "MAPBOX";
  steps: WalkingRouteStep[];
  supportedPct: number;
}

export interface WalkingRoutesResult {
  preference: CrowdPreference;
  rankingStatus: RouteRankingStatus;
  recommendedRouteId: string | null;
  routes: WalkingRoute[];
}

export interface WalkingRouteSearchRequest {
  destination: MapboxJourneyLocation;
  origin: JourneyLocation;
  preference: CrowdPreference;
}
