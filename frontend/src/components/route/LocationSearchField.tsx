import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import {
  MAPBOX_CONFIG,
  createMapboxSearchSessionToken,
  isMapboxConfigured,
  retrieveMapboxPlace,
  suggestMapboxPlaces,
  type MapboxSearchSuggestion,
} from "../../services/mapbox";
import type {
  JourneyLocation,
  MapboxSelectedLocation,
} from "../../types/route";

interface LocationSearchFieldProps {
  error?: string;
  id: string;
  label: string;
  labelAction?: ReactNode;
  onSelect: (location: MapboxSelectedLocation) => void;
  onTextChange: (value: string) => void;
  placeholder: string;
  selectedLocation: JourneyLocation | null;
  status?: string | null;
  value: string;
}

function suggestionSecondaryText(suggestion: MapboxSearchSuggestion): string {
  return (
    suggestion.fullAddress ??
    [suggestion.address, suggestion.placeFormatted]
      .filter((part): part is string => Boolean(part))
      .join(", ")
  );
}

function selectedLocationDescription(location: JourneyLocation): string {
  return location.source === "MAPBOX"
    ? location.fullAddress
    : location.label;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function LocationSearchField({
  error,
  id,
  label,
  labelAction,
  onSelect,
  onTextChange,
  placeholder,
  selectedLocation,
  status,
  value,
}: LocationSearchFieldProps) {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [hasCompletedSuggest, setHasCompletedSuggest] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<MapboxSearchSuggestion[]>([]);
  const requestGenerationRef = useRef(0);
  const retrieveControllerRef = useRef<AbortController | null>(null);
  const sessionTokenRef = useRef(createMapboxSearchSessionToken());
  const suggestControllerRef = useRef<AbortController | null>(null);

  const listId = `${id}-suggestions`;
  const statusId = `${id}-search-status`;
  const selectionId = `${id}-selection`;
  const errorId = `${id}-error`;
  const supplementalStatusId = `${id}-supplemental-status`;
  const query = value.trim();
  const search = MAPBOX_CONFIG.searchBoxRequest;
  const showSuggestions = isFocused && isOpen && suggestions.length > 0;

  useEffect(() => {
    suggestControllerRef.current?.abort();
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;
    setActiveIndex(-1);

    if (selectedLocation || query.length < search.minimumQueryLength) {
      setHasCompletedSuggest(false);
      setIsSuggesting(false);
      setSearchError(null);
      setSuggestions([]);
      return;
    }

    if (!isMapboxConfigured()) {
      setHasCompletedSuggest(false);
      setIsSuggesting(false);
      setSearchError(
        "Place search is unavailable because the Mapbox public token is not configured.",
      );
      setSuggestions([]);
      return;
    }

    const controller = new AbortController();
    suggestControllerRef.current = controller;
    setHasCompletedSuggest(false);
    setIsSuggesting(true);
    setSearchError(null);

    const timer = window.setTimeout(() => {
      void suggestMapboxPlaces(
        query,
        sessionTokenRef.current,
        controller.signal,
      )
        .then((nextSuggestions) => {
          if (
            controller.signal.aborted ||
            requestGenerationRef.current !== generation
          ) {
            return;
          }

          setSuggestions(nextSuggestions);
          setHasCompletedSuggest(true);
          setIsOpen(true);
        })
        .catch((requestError: unknown) => {
          if (controller.signal.aborted || isAbortError(requestError)) {
            return;
          }

          if (requestGenerationRef.current === generation) {
            setSuggestions([]);
            setHasCompletedSuggest(false);
            setSearchError(
              "We could not load place suggestions. Check your connection and try again.",
            );
          }
        })
        .finally(() => {
          if (requestGenerationRef.current === generation) {
            setIsSuggesting(false);
          }
        });
    }, search.debounceMs);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, search.debounceMs, search.minimumQueryLength, selectedLocation]);

  useEffect(
    () => () => {
      suggestControllerRef.current?.abort();
      retrieveControllerRef.current?.abort();
    },
    [],
  );

  function changeText(nextValue: string) {
    const isStartingNewSession = !nextValue.trim() && Boolean(value.trim());
    suggestControllerRef.current?.abort();
    retrieveControllerRef.current?.abort();
    requestGenerationRef.current += 1;
    setActiveIndex(-1);
    setHasCompletedSuggest(false);
    setIsOpen(true);
    setIsRetrieving(false);
    setSearchError(null);
    setSuggestions([]);

    if (isStartingNewSession) {
      sessionTokenRef.current = createMapboxSearchSessionToken();
    }

    onTextChange(nextValue);
  }

  async function selectSuggestion(suggestion: MapboxSearchSuggestion) {
    suggestControllerRef.current?.abort();
    retrieveControllerRef.current?.abort();
    requestGenerationRef.current += 1;

    const controller = new AbortController();
    retrieveControllerRef.current = controller;
    const completedSessionToken = sessionTokenRef.current;
    setActiveIndex(-1);
    setIsRetrieving(true);
    setIsSuggesting(false);
    setSearchError(null);

    try {
      const location = await retrieveMapboxPlace(
        suggestion.mapboxId,
        completedSessionToken,
        controller.signal,
      );
      if (controller.signal.aborted) {
        return;
      }

      onSelect(location);
      setHasCompletedSuggest(false);
      setIsOpen(false);
      setSuggestions([]);

      // A successful retrieve completes this suggest -> retrieve session. The
      // next independent interaction starts with a fresh token for this field.
      sessionTokenRef.current = createMapboxSearchSessionToken();
    } catch (requestError: unknown) {
      if (controller.signal.aborted || isAbortError(requestError)) {
        return;
      }

      setSearchError(
        "We could not confirm that place. Choose the suggestion again or try another result.",
      );
    } finally {
      if (retrieveControllerRef.current === controller) {
        retrieveControllerRef.current = null;
        setIsRetrieving(false);
      }
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setActiveIndex(-1);
      setIsOpen(false);
      return;
    }

    if (!showSuggestions) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) =>
        current <= 0 ? suggestions.length - 1 : current - 1,
      );
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      void selectSuggestion(suggestions[activeIndex]);
    }
  }

  const describedBy = [
    error ? errorId : null,
    status ? supplementalStatusId : null,
    selectedLocation ? selectionId : null,
    isSuggesting || isRetrieving || searchError || hasCompletedSuggest
      ? statusId
      : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="field location-search">
      <div className="field-label-row">
        <label htmlFor={id}>{label}</label>
        {labelAction}
      </div>

      <div className="location-search__control">
        <input
          aria-activedescendant={
            showSuggestions && activeIndex >= 0
              ? `${id}-suggestion-${activeIndex}`
              : undefined
          }
          aria-autocomplete="list"
          aria-controls={listId}
          aria-describedby={describedBy || undefined}
          aria-expanded={showSuggestions}
          aria-invalid={Boolean(error || searchError)}
          autoComplete="off"
          id={id}
          name={id}
          onBlur={() => {
            setIsFocused(false);
            setIsOpen(false);
          }}
          onChange={(event) => changeText(event.target.value)}
          onFocus={() => {
            setIsFocused(true);
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          role="combobox"
          type="text"
          value={value}
        />
        {value && (
          <button
            aria-label={`Clear ${label.toLowerCase()}`}
            className="location-search__clear"
            onClick={() => changeText("")}
            type="button"
          >
            Clear
          </button>
        )}
      </div>

      {showSuggestions && (
        <div
          className="location-search__suggestions"
          id={listId}
          role="listbox"
        >
          {suggestions.map((suggestion, index) => (
            <button
              aria-selected={activeIndex === index}
              className={
                activeIndex === index
                  ? "location-search__suggestion location-search__suggestion--active"
                  : "location-search__suggestion"
              }
              id={`${id}-suggestion-${index}`}
              key={suggestion.mapboxId}
              onClick={() => void selectSuggestion(suggestion)}
              onMouseDown={(event) => event.preventDefault()}
              role="option"
              type="button"
            >
              <strong>{suggestion.name}</strong>
              <span>{suggestionSecondaryText(suggestion)}</span>
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      )}

      {status && (
        <p
          className="field-status"
          id={supplementalStatusId}
          role="status"
        >
          {status}
        </p>
      )}

      {selectedLocation && (
        <p className="field-status field-status--selected" id={selectionId}>
          Selected: {selectedLocationDescription(selectedLocation)}
        </p>
      )}

      {import.meta.env.DEV && selectedLocation && (
        <p className="field-hint location-search__development-check">
          Development check: longitude {selectedLocation.longitude.toFixed(6)},
          latitude {selectedLocation.latitude.toFixed(6)}
        </p>
      )}

      <div aria-live="polite" id={statusId}>
        {isSuggesting && <p className="field-status">Searching places...</p>}
        {isRetrieving && <p className="field-status">Confirming place...</p>}
        {!isSuggesting &&
          !isRetrieving &&
          hasCompletedSuggest &&
          suggestions.length === 0 && (
            <p className="field-status">
              No matching places found. Try a more specific Melbourne place or
              address.
            </p>
          )}
        {searchError && <p className="field-error">{searchError}</p>}
      </div>
    </div>
  );
}

export default LocationSearchField;
