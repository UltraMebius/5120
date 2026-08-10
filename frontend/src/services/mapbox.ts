import type { MapboxSelectedLocation } from "../types/route";

const publicToken = (
  import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN as string | undefined
)?.trim();

const MELBOURNE_CBD_PROXIMITY = "144.9631,-37.8136";

export const MAPBOX_CONFIG = Object.freeze({
  geocodingBaseUrl: "https://api.mapbox.com/search/geocode/v6",
  publicToken: publicToken ?? "",
  searchBoxBaseUrl: "https://api.mapbox.com/search/searchbox/v1",
  searchBoxRequest: Object.freeze({
    country: "AU",
    debounceMs: 300,
    language: "en",
    limit: 5,
    minimumQueryLength: 3,
    proximity: MELBOURNE_CBD_PROXIMITY,
    types: "poi,address,place,locality,neighborhood,street",
  }),
});

export function isMapboxConfigured(): boolean {
  return MAPBOX_CONFIG.publicToken.length > 0;
}

export interface MapboxSearchSuggestion {
  address?: string;
  featureType: string;
  fullAddress?: string;
  mapboxId: string;
  name: string;
  placeFormatted: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function parseSuggestion(value: unknown): MapboxSearchSuggestion | null {
  if (!isRecord(value)) {
    return null;
  }

  const name = readOptionalString(value.name);
  const mapboxId = readOptionalString(value.mapbox_id);
  const featureType = readOptionalString(value.feature_type);
  const placeFormatted = readOptionalString(value.place_formatted);

  if (!name || !mapboxId || !featureType || !placeFormatted) {
    return null;
  }

  return {
    address: readOptionalString(value.address),
    featureType,
    fullAddress: readOptionalString(value.full_address),
    mapboxId,
    name,
    placeFormatted,
  };
}

function parseSelectedLocation(value: unknown): MapboxSelectedLocation {
  if (!isRecord(value) || value.type !== "FeatureCollection") {
    throw new Error("Mapbox returned an invalid retrieve response.");
  }

  const features = value.features;
  if (!Array.isArray(features) || features.length === 0) {
    throw new Error("Mapbox retrieve returned no feature.");
  }

  const feature = features[0];
  if (!isRecord(feature) || !isRecord(feature.geometry)) {
    throw new Error("Mapbox retrieve returned a malformed feature.");
  }

  const coordinates = feature.geometry.coordinates;
  const properties = feature.properties;
  if (
    feature.geometry.type !== "Point" ||
    !Array.isArray(coordinates) ||
    coordinates.length < 2 ||
    !isRecord(properties)
  ) {
    throw new Error("Mapbox retrieve returned a malformed point.");
  }

  const longitude = coordinates[0];
  const latitude = coordinates[1];
  const mapboxId = readOptionalString(properties.mapbox_id);
  const name =
    readOptionalString(properties.name_preferred) ??
    readOptionalString(properties.name);

  if (
    typeof longitude !== "number" ||
    !Number.isFinite(longitude) ||
    typeof latitude !== "number" ||
    !Number.isFinite(latitude) ||
    !mapboxId ||
    !name
  ) {
    throw new Error("Mapbox retrieve response is missing required fields.");
  }

  const formattedAddress = [
    readOptionalString(properties.address),
    readOptionalString(properties.place_formatted),
  ]
    .filter((part): part is string => Boolean(part))
    .join(", ");
  const fullAddress =
    readOptionalString(properties.full_address) ?? (formattedAddress || name);

  return { fullAddress, latitude, longitude, mapboxId, name };
}

async function readJson(response: Response): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`Mapbox Search Box request failed (${response.status}).`);
  }

  try {
    return (await response.json()) as unknown;
  } catch {
    throw new Error("Mapbox Search Box returned invalid JSON.");
  }
}

export function createMapboxSearchSessionToken(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}

export async function suggestMapboxPlaces(
  query: string,
  sessionToken: string,
  signal: AbortSignal,
): Promise<MapboxSearchSuggestion[]> {
  if (!isMapboxConfigured()) {
    throw new Error("Mapbox public token is not configured.");
  }

  const search = MAPBOX_CONFIG.searchBoxRequest;
  const parameters = new URLSearchParams({
    access_token: MAPBOX_CONFIG.publicToken,
    country: search.country,
    language: search.language,
    limit: String(search.limit),
    proximity: search.proximity,
    q: query,
    session_token: sessionToken,
    types: search.types,
  });
  const response = await fetch(
    `${MAPBOX_CONFIG.searchBoxBaseUrl}/suggest?${parameters.toString()}`,
    { headers: { Accept: "application/json" }, signal },
  );
  const body = await readJson(response);

  if (!isRecord(body) || !Array.isArray(body.suggestions)) {
    throw new Error("Mapbox returned an invalid suggestion response.");
  }

  return body.suggestions
    .map(parseSuggestion)
    .filter((suggestion): suggestion is MapboxSearchSuggestion =>
      Boolean(suggestion),
    )
    .slice(0, search.limit);
}

export async function retrieveMapboxPlace(
  mapboxId: string,
  sessionToken: string,
  signal: AbortSignal,
): Promise<MapboxSelectedLocation> {
  if (!isMapboxConfigured()) {
    throw new Error("Mapbox public token is not configured.");
  }

  const parameters = new URLSearchParams({
    access_token: MAPBOX_CONFIG.publicToken,
    language: MAPBOX_CONFIG.searchBoxRequest.language,
    session_token: sessionToken,
  });
  const response = await fetch(
    `${MAPBOX_CONFIG.searchBoxBaseUrl}/retrieve/${encodeURIComponent(mapboxId)}?${parameters.toString()}`,
    { headers: { Accept: "application/json" }, signal },
  );

  return parseSelectedLocation(await readJson(response));
}

// Search Box /suggest and /retrieve are active in Phase 3A. Geocoding v6 and
// Directions remain separate later-phase boundaries and are not called here.
