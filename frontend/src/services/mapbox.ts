const publicToken = (
  import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN as string | undefined
)?.trim();

export const MAPBOX_PHASE_2_CONFIG = Object.freeze({
  directionsBaseUrl: "https://api.mapbox.com/directions/v5",
  directionsProfile: "mapbox/walking",
  geocodingBaseUrl: "https://api.mapbox.com/search/geocode/v6",
  publicToken: publicToken ?? "",
  routeRequest: Object.freeze({
    alternatives: true,
    geometries: "geojson",
    language: "en",
    overview: "full",
    steps: true,
  }),
});

export function isMapboxConfigured(): boolean {
  return MAPBOX_PHASE_2_CONFIG.publicToken.length > 0;
}

// The smoke test uses only publicToken for Mapbox GL basemap resources. Search,
// Geocoding API v6 and Directions remain later-phase integration boundaries.
