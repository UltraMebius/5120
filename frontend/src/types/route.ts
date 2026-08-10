import type {
  CoverageStatus,
  CrowdPreference,
  FrontendCrowdLevel,
  InternalCrowdLevel,
} from "./crowd";

export interface Coordinate {
  latitude: number;
  longitude: number;
}

export interface JourneyLocation {
  coordinates?: Coordinate;
  label: string;
  source: "CURRENT_LOCATION" | "MANUAL";
}

export type ManeuverDirection = "LEFT" | "RIGHT" | "STRAIGHT";

export interface Maneuver {
  direction: ManeuverDirection;
  distanceM: number;
  instruction: string;
}

export interface WalkingRoute {
  coverageStatus?: CoverageStatus;
  crowdLevel: FrontendCrowdLevel;
  distanceKm: number;
  durationMin: number;
  id: string;
  internalCrowdLevel?: InternalCrowdLevel;
  maneuvers?: Maneuver[];
  name: string;
  recommended: boolean;
}

export interface WalkingRouteSearchRequest {
  destination: JourneyLocation;
  origin: JourneyLocation;
  preference: CrowdPreference;
}
