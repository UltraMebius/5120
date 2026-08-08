import { useState, type FormEvent } from "react";

interface RouteSearchFormProps {
  isLoading: boolean;
  onSearch: (origin: string, destination: string) => Promise<void>;
}

interface FormErrors {
  origin?: string;
  destination?: string;
}

function RouteSearchForm({ isLoading, onSearch }: RouteSearchFormProps) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});

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

    void onSearch(trimmedOrigin, trimmedDestination);
  }

  return (
    <form className="search-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="origin">Origin</label>
        <input
          id="origin"
          name="origin"
          type="text"
          value={origin}
          onChange={(event) => {
            setOrigin(event.target.value);
            if (errors.origin) {
              setErrors((current) => ({ ...current, origin: undefined }));
            }
          }}
          placeholder="e.g. Flinders Street Station"
          aria-invalid={Boolean(errors.origin)}
          aria-describedby={errors.origin ? "origin-error" : undefined}
        />
        {errors.origin && (
          <p id="origin-error" className="field-error">
            {errors.origin}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="destination">Destination</label>
        <input
          id="destination"
          name="destination"
          type="text"
          value={destination}
          onChange={(event) => {
            setDestination(event.target.value);
            if (errors.destination) {
              setErrors((current) => ({ ...current, destination: undefined }));
            }
          }}
          placeholder="e.g. State Library Victoria"
          aria-invalid={Boolean(errors.destination)}
          aria-describedby={
            errors.destination ? "destination-error" : undefined
          }
        />
        {errors.destination && (
          <p id="destination-error" className="field-error">
            {errors.destination}
          </p>
        )}
      </div>

      <button type="submit" disabled={isLoading}>
        {isLoading ? "Finding Routes..." : "Find Routes"}
      </button>
    </form>
  );
}

export default RouteSearchForm;
