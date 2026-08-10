import type { GeolocationJourneyLocation } from "../types/route";

export const GEOLOCATION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  maximumAge: 30_000,
  timeout: 10_000,
};

type GeolocationFailureKind =
  | "PERMISSION_DENIED"
  | "POSITION_UNAVAILABLE"
  | "TIMEOUT"
  | "UNSUPPORTED";

const ERROR_MESSAGES: Record<GeolocationFailureKind, string> = {
  PERMISSION_DENIED:
    "Location access was denied. Allow location access or enter a starting point manually.",
  POSITION_UNAVAILABLE:
    "Your location could not be determined. Enter a starting point manually.",
  TIMEOUT:
    "Location request timed out. Try again or enter a starting point manually.",
  UNSUPPORTED:
    "Location is not available in this browser. Enter a starting point manually.",
};

class GeolocationRequestError extends Error {
  readonly kind: GeolocationFailureKind;

  constructor(kind: GeolocationFailureKind) {
    super(ERROR_MESSAGES[kind]);
    this.name = "GeolocationRequestError";
    this.kind = kind;
  }
}

function isValidCoordinate(
  latitude: number,
  longitude: number,
): boolean {
  return (
    Number.isFinite(latitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    Number.isFinite(longitude) &&
    longitude >= -180 &&
    longitude <= 180
  );
}

function failureKindFromPositionError(
  error: GeolocationPositionError,
): GeolocationFailureKind {
  if (error.code === 1) {
    return "PERMISSION_DENIED";
  }
  if (error.code === 3) {
    return "TIMEOUT";
  }
  return "POSITION_UNAVAILABLE";
}

export function geolocationErrorMessage(error: unknown): string {
  return error instanceof GeolocationRequestError
    ? error.message
    : ERROR_MESSAGES.POSITION_UNAVAILABLE;
}

export function getCurrentJourneyLocation(
  geolocation: Geolocation | undefined =
    typeof navigator === "undefined" ? undefined : navigator.geolocation,
): Promise<GeolocationJourneyLocation> {
  if (!geolocation) {
    return Promise.reject(new GeolocationRequestError("UNSUPPORTED"));
  }

  return new Promise((resolve, reject) => {
    try {
      geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          if (!isValidCoordinate(latitude, longitude)) {
            reject(new GeolocationRequestError("POSITION_UNAVAILABLE"));
            return;
          }

          resolve({
            label: "Current location",
            latitude,
            longitude,
            name: "Current location",
            source: "GEOLOCATION",
          });
        },
        (error) => {
          reject(
            new GeolocationRequestError(
              failureKindFromPositionError(error),
            ),
          );
        },
        GEOLOCATION_OPTIONS,
      );
    } catch {
      reject(new GeolocationRequestError("POSITION_UNAVAILABLE"));
    }
  });
}
