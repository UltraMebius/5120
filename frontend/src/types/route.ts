import type { CrowdPreference } from "./crowd";

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

export interface LegacyJourneyLocation {
  coordinates?: Coordinate;
  label: string;
  source: "CURRENT_LOCATION" | "MANUAL";
}

export type JourneyLocation = MapboxJourneyLocation | LegacyJourneyLocation;

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
  distanceMeters: number;
  durationSeconds: number;
  geometry: GeoJsonLineString;
  id: string;
  name: string;
  routeIndex: number;
  source: "MAPBOX";
  steps: WalkingRouteStep[];
}

export interface WalkingRouteSearchRequest {
  destination: MapboxJourneyLocation;
  origin: MapboxJourneyLocation;
  preference: CrowdPreference;
}
