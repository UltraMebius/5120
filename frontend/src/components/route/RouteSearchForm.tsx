import { useState, type FormEvent } from "react";

import type { CrowdPreference } from "../../types/crowd";
import type {
  Coordinate,
  JourneyLocation,
  WalkingRouteSearchRequest,
} from "../../types/route";
import CrowdPreferenceSelector from "../crowd/CrowdPreferenceSelector";

interface RouteSearchFormProps {
  initialDestination?: JourneyLocation | null;
  initialOrigin?: JourneyLocation | null;
  initialPreference: CrowdPreference;
  isLoading: boolean;
  onSearch: (request: WalkingRouteSearchRequest) => Promise<void>;
}

interface FormErrors {
  destination?: string;
  origin?: string;
}

function RouteSearchForm({
  initialDestination,
  initialOrigin,
  initialPreference,
  isLoading,
  onSearch,
}: RouteSearchFormProps) {
  const [origin, setOrigin] = useState(initialOrigin?.label ?? "");
  const [destination, setDestination] = useState(
    initialDestination?.label ?? "",
  );
  const [originCoordinates, setOriginCoordinates] = useState<
    Coordinate | undefined
  >(initialOrigin?.coordinates);
  const [preference, setPreference] =
    useState<CrowdPreference>(initialPreference);
  const [errors, setErrors] = useState<FormErrors>({});
  const [locationStatus, setLocationStatus] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState(false);

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setLocationStatus("Current location is not supported by this browser.");
      return;
    }

    setIsLocating(true);
    setLocationStatus("Requesting your current location…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin("Current location");
        setOriginCoordinates({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
        setErrors((current) => ({ ...current, origin: undefined }));
        setLocationStatus("Current location selected.");
        setIsLocating(false);
      },
      () => {
        setLocationStatus(
          "We could not access your location. Enter an origin instead.",
        );
        setIsLocating(false);
      },
      { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedOrigin = origin.trim();
    const trimmedDestination = destination.trim();
    const nextErrors: FormErrors = {};

    if (!trimmedOrigin) {
      nextErrors.origin = "Origin is required.";
    }

    if (!trimmedDestination) {
      nextErrors.destination = "Destination is required.";
    }

    setErrors(nextErrors);

    if (nextErrors.origin || nextErrors.destination) {
      return;
    }

    void onSearch({
      destination: {
        label: trimmedDestination,
        source: "MANUAL",
      },
      origin: {
        coordinates: originCoordinates,
        label: trimmedOrigin,
        source: originCoordinates ? "CURRENT_LOCATION" : "MANUAL",
      },
      preference,
    });
  }

  return (
    <form className="search-form" noValidate onSubmit={handleSubmit}>
      <div className="location-fields">
        <div className="location-rail" aria-hidden="true">
          <span className="location-dot location-dot--origin" />
          <span className="location-line" />
          <span className="location-dot location-dot--destination" />
        </div>

        <div className="field">
          <div className="field-label-row">
            <label htmlFor="origin">Starting point</label>
            <button
              className="text-button"
              disabled={isLocating}
              onClick={useCurrentLocation}
              type="button"
            >
              <span aria-hidden="true">◎</span>{" "}
              {isLocating ? "Locating…" : "Use my location"}
            </button>
          </div>
          <input
            aria-describedby={errors.origin ? "origin-error" : undefined}
            aria-invalid={Boolean(errors.origin)}
            id="origin"
            name="origin"
            onChange={(event) => {
              setOrigin(event.target.value);
              setOriginCoordinates(undefined);
              if (errors.origin) {
                setErrors((current) => ({ ...current, origin: undefined }));
              }
            }}
            placeholder="Enter a Melbourne CBD address"
            type="text"
            value={origin}
          />
          {errors.origin && (
            <p className="field-error" id="origin-error">
              {errors.origin}
            </p>
          )}
          {locationStatus && (
            <p className="field-status" role="status">
              {locationStatus}
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="destination">Destination</label>
          <input
            aria-describedby={
              errors.destination ? "destination-error" : undefined
            }
            aria-invalid={Boolean(errors.destination)}
            id="destination"
            name="destination"
            onChange={(event) => {
              setDestination(event.target.value);
              if (errors.destination) {
                setErrors((current) => ({
                  ...current,
                  destination: undefined,
                }));
              }
            }}
            placeholder="Where are you going?"
            type="text"
            value={destination}
          />
          {errors.destination && (
            <p className="field-error" id="destination-error">
              {errors.destination}
            </p>
          )}
        </div>
      </div>

      <p className="integration-note">
        Address suggestions will connect to Mapbox Geocoding API v6 in a later
        phase. Manual text currently loads preview routes.
      </p>

      <CrowdPreferenceSelector onChange={setPreference} value={preference} />

      <p className="crowd-disclaimer">
        Crowd levels are relative estimates based on City of Melbourne
        pedestrian activity data. They are not medical or safety thresholds.
      </p>

      <button
        className="button button--primary button--large"
        disabled={isLoading}
        type="submit"
      >
        {isLoading ? "Finding preview routes…" : "Find sensory-friendly routes"}
        <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}

export default RouteSearchForm;
