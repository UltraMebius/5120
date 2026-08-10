import { useState, type FormEvent } from "react";

import type { CrowdPreference } from "../../types/crowd";
import type {
  Coordinate,
  JourneyLocation,
  MapboxJourneyLocation,
  MapboxSelectedLocation,
  WalkingRouteSearchRequest,
} from "../../types/route";
import CrowdPreferenceSelector from "../crowd/CrowdPreferenceSelector";
import LocationSearchField from "./LocationSearchField";

interface RouteSearchFormProps {
  initialDestination?: JourneyLocation | null;
  initialOrigin?: JourneyLocation | null;
  initialPreference: CrowdPreference;
  isLoading: boolean;
  onDraftLocationChange: (
    field: "destination" | "origin",
    location: JourneyLocation | null,
  ) => void;
  onSearch: (request: WalkingRouteSearchRequest) => Promise<void>;
}

interface FormErrors {
  destination?: string;
  origin?: string;
}

interface LocationFieldState {
  selectedLocation: MapboxSelectedLocation | null;
  text: string;
}

function selectedLocationFromJourney(
  location?: JourneyLocation | null,
): MapboxSelectedLocation | null {
  if (!location || location.source !== "MAPBOX") {
    return null;
  }

  return {
    fullAddress: location.fullAddress,
    latitude: location.latitude,
    longitude: location.longitude,
    mapboxId: location.mapboxId,
    name: location.name,
  };
}

function journeyLocationFromSelection(
  location: MapboxSelectedLocation,
): MapboxJourneyLocation {
  return {
    ...location,
    label: location.name,
    source: "MAPBOX",
  };
}

function RouteSearchForm({
  initialDestination,
  initialOrigin,
  initialPreference,
  isLoading,
  onDraftLocationChange,
  onSearch,
}: RouteSearchFormProps) {
  const [origin, setOrigin] = useState<LocationFieldState>({
    selectedLocation: selectedLocationFromJourney(initialOrigin),
    text: initialOrigin?.label ?? "",
  });
  const [destination, setDestination] = useState<LocationFieldState>({
    selectedLocation: selectedLocationFromJourney(initialDestination),
    text: initialDestination?.label ?? "",
  });
  const [originCoordinates, setOriginCoordinates] = useState<
    Coordinate | undefined
  >(
    initialOrigin?.source === "CURRENT_LOCATION"
      ? initialOrigin.coordinates
      : undefined,
  );
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
    setLocationStatus("Requesting your current location...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({ selectedLocation: null, text: "Current location" });
        setOriginCoordinates({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
        onDraftLocationChange("origin", null);
        setErrors((current) => ({ ...current, origin: undefined }));
        setLocationStatus(
          "Current location is available, but Phase 3A submission still requires a Mapbox place selection.",
        );
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

  function changeOriginText(text: string) {
    if (origin.selectedLocation) {
      onDraftLocationChange("origin", null);
    }
    setOrigin({ selectedLocation: null, text });
    setOriginCoordinates(undefined);
    setLocationStatus(null);
    if (errors.origin) {
      setErrors((current) => ({ ...current, origin: undefined }));
    }
  }

  function changeDestinationText(text: string) {
    if (destination.selectedLocation) {
      onDraftLocationChange("destination", null);
    }
    setDestination({ selectedLocation: null, text });
    if (errors.destination) {
      setErrors((current) => ({ ...current, destination: undefined }));
    }
  }

  function selectOrigin(location: MapboxSelectedLocation) {
    setOrigin({ selectedLocation: location, text: location.name });
    setOriginCoordinates(undefined);
    setLocationStatus(null);
    setErrors((current) => ({ ...current, origin: undefined }));
    onDraftLocationChange("origin", journeyLocationFromSelection(location));
  }

  function selectDestination(location: MapboxSelectedLocation) {
    setDestination({ selectedLocation: location, text: location.name });
    setErrors((current) => ({ ...current, destination: undefined }));
    onDraftLocationChange(
      "destination",
      journeyLocationFromSelection(location),
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedOrigin = origin.text.trim();
    const trimmedDestination = destination.text.trim();
    const nextErrors: FormErrors = {};

    if (!trimmedOrigin) {
      nextErrors.origin = "Origin is required.";
    } else if (!origin.selectedLocation) {
      nextErrors.origin =
        "Select a starting point from the Mapbox suggestions.";
    }

    if (!trimmedDestination) {
      nextErrors.destination = "Destination is required.";
    } else if (!destination.selectedLocation) {
      nextErrors.destination =
        "Select a destination from the Mapbox suggestions.";
    }

    setErrors(nextErrors);

    if (
      nextErrors.origin ||
      nextErrors.destination ||
      !origin.selectedLocation ||
      !destination.selectedLocation
    ) {
      return;
    }

    void onSearch({
      destination: journeyLocationFromSelection(
        destination.selectedLocation,
      ),
      origin: journeyLocationFromSelection(origin.selectedLocation),
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

        <LocationSearchField
          error={errors.origin}
          id="origin"
          label="Starting point"
          labelAction={
            <button
              className="text-button"
              disabled={isLocating}
              onClick={useCurrentLocation}
              type="button"
            >
              <span aria-hidden="true">◎</span>{" "}
              {isLocating ? "Locating..." : "Use my location"}
            </button>
          }
          onSelect={selectOrigin}
          onTextChange={changeOriginText}
          placeholder="Search for a Melbourne place or address"
          selectedLocation={origin.selectedLocation}
          status={locationStatus}
          value={origin.text}
        />

        <LocationSearchField
          error={errors.destination}
          id="destination"
          label="Destination"
          onSelect={selectDestination}
          onTextChange={changeDestinationText}
          placeholder="Search for a Melbourne place or address"
          selectedLocation={destination.selectedLocation}
          value={destination.text}
        />
      </div>

      <p className="integration-note">
        Select both places from Mapbox suggestions. CalmWay will request real
        walking routes through its backend; crowd ranking is not connected yet.
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
        {isLoading ? "Loading walking routes..." : "Find walking routes"}
        <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}

export default RouteSearchForm;
