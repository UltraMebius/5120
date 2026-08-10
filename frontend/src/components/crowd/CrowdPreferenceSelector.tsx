import {
  CROWD_PREFERENCE_OPTIONS,
  type CrowdPreference,
} from "../../types/crowd";
import CrowdBadge from "./CrowdBadge";

interface CrowdPreferenceSelectorProps {
  onChange: (preference: CrowdPreference) => void;
  value: CrowdPreference;
}

function CrowdPreferenceSelector({
  onChange,
  value,
}: CrowdPreferenceSelectorProps) {
  return (
    <fieldset className="preference-fieldset">
      <legend>Choose your crowd tolerance</legend>
      <p className="field-hint">
        Select one option. You can change it before comparing routes.
      </p>

      <div className="preference-grid">
        {CROWD_PREFERENCE_OPTIONS.map((option) => (
          <label
            className={`preference-option${
              value === option.backendPreference
                ? " preference-option--selected"
                : ""
            }`}
            key={option.backendPreference}
          >
            <input
              checked={value === option.backendPreference}
              name="crowd-preference"
              onChange={() => onChange(option.backendPreference)}
              type="radio"
              value={option.backendPreference}
            />
            <span className="preference-option__content">
              <span className="preference-option__heading">
                <CrowdBadge level={option.uiLevel} />
                <span className="preference-option__check" aria-hidden="true">
                  ✓
                </span>
              </span>
              <span className="preference-option__description">
                {option.description}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default CrowdPreferenceSelector;
