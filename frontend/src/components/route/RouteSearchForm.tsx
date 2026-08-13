import { useRef, useState, type FormEvent } from "react";

import {
  geolocationErrorMessage,
  getCurrentJourneyLocation,
} from "../../services/geolocation";
import type {
  JourneyLocation,
  MapboxJourneyLocation,
  MapboxSelectedLocation,
} from "../../types/route";
import type { RouteOptionsSearchRequest } from "../../types/routeOptions";
import LocationSearchField from "./LocationSearchField";

interface RouteSearchFormProps {
  initialDestination?: JourneyLocation | null;
  initialOrigin?: JourneyLocation | null;
  isLoading: boolean;
  onDraftLocationChange: (
    field: "destination" | "origin",
    location: JourneyLocation | null,
  ) => void;
  onSearch: (request: RouteOptionsSearchRequest) => Promise<void>;
}

interface FormErrors {
  destination?: string;
  origin?: string;
}

interface LocationFieldState {
  selectedLocation: JourneyLocation | null;
  text: string;
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
  isLoading,
  onDraftLocationChange,
  onSearch,
}: RouteSearchFormProps) {
  const [origin, setOrigin] = useState<LocationFieldState>({
    selectedLocation: initialOrigin ?? null,
    text: initialOrigin?.label ?? "",
  });
  const [destination, setDestination] = useState<LocationFieldState>({
    selectedLocation: initialDestination ?? null,
    text: initialDestination?.label ?? "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [locationError, setLocationError] = useState<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const isLocatingRef = useRef(false);
  const isSubmittingRef = useRef(false);

  async function useCurrentLocation() {
    if (isLocatingRef.current) {
      return;
    }

    isLocatingRef.current = true;
    setIsLocating(true);
    setLocationError(null);
    setLocationStatus("Requesting your current location...");

    try {
      const currentLocation = await getCurrentJourneyLocation();
      setOrigin({
        selectedLocation: currentLocation,
        text: currentLocation.label,
      });
      onDraftLocationChange("origin", currentLocation);
      setErrors((current) => ({ ...current, origin: undefined }));
      setLocationStatus("Current location selected.");
    } catch (error: unknown) {
      setLocationError(geolocationErrorMessage(error));
      setLocationStatus(null);
    } finally {
      isLocatingRef.current = false;
      setIsLocating(false);
    }
  }

  function changeOriginText(text: string) {
    if (origin.selectedLocation) {
      onDraftLocationChange("origin", null);
    }
    setOrigin({ selectedLocation: null, text });
    setLocationError(null);
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
    const journeyLocation = journeyLocationFromSelection(location);
    setOrigin({ selectedLocation: journeyLocation, text: location.name });
    setLocationError(null);
    setLocationStatus(null);
    setErrors((current) => ({ ...current, origin: undefined }));
    onDraftLocationChange("origin", journeyLocation);
  }

  function selectDestination(location: MapboxSelectedLocation) {
    const journeyLocation = journeyLocationFromSelection(location);
    setDestination({ selectedLocation: journeyLocation, text: location.name });
    setErrors((current) => ({ ...current, destination: undefined }));
    onDraftLocationChange("destination", journeyLocation);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isLoading || isLocatingRef.current || isSubmittingRef.current) {
      return;
    }

    const trimmedOrigin = origin.text.trim();
    const trimmedDestination = destination.text.trim();
    const nextErrors: FormErrors = {};

    if (!trimmedOrigin) {
      nextErrors.origin = "Origin is required.";
    } else if (!origin.selectedLocation) {
      nextErrors.origin = "Choose a starting point from the suggestions.";
    }

    if (!trimmedDestination) {
      nextErrors.destination = "Destination is required.";
    } else if (destination.selectedLocation?.source !== "MAPBOX") {
      nextErrors.destination = "Choose a destination from the suggestions.";
    }

    setErrors(nextErrors);

    if (
      nextErrors.origin ||
      nextErrors.destination ||
      !origin.selectedLocation ||
      destination.selectedLocation?.source !== "MAPBOX"
    ) {
      return;
    }

    isSubmittingRef.current = true;
    void onSearch({
      destination: destination.selectedLocation,
      origin: origin.selectedLocation,
    }).finally(() => {
      isSubmittingRef.current = false;
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
          error={locationError ?? errors.origin}
          id="origin"
          label="From"
          labelAction={
            <button
              className="text-button"
              disabled={isLocating}
              aria-busy={isLocating}
              onClick={() => void useCurrentLocation()}
              type="button"
            >
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
          label="To"
          onSelect={selectDestination}
          onTextChange={changeDestinationText}
          placeholder="Search for a Melbourne place or address"
          selectedLocation={destination.selectedLocation}
          value={destination.text}
        />
      </div>

      <p className="crowd-disclaimer">
        Pedestrian activity is an estimate based on nearby sensors.
      </p>

      <button
        className="button button--primary button--large"
        disabled={isLoading || isLocating}
        type="submit"
      >
        {isLoading
          ? "Finding walking routes..."
          : "Find sensory-friendly routes"}
        <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}

export default RouteSearchForm;
