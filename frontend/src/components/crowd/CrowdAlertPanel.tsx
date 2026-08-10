import CrowdBadge from "./CrowdBadge";

interface CrowdAlertPanelProps {
  alternativeAvailable: boolean;
  onContinue: () => void;
  onStartAlternative: () => void;
}

function CrowdAlertPanel({
  alternativeAvailable,
  onContinue,
  onStartAlternative,
}: CrowdAlertPanelProps) {
  return (
    <div className="alert-backdrop" role="presentation">
      <section
        aria-labelledby="crowd-alert-title"
        aria-modal="true"
        className="crowd-alert"
        role="dialog"
      >
        <div className="crowd-alert__icon" aria-hidden="true">
          !
        </div>
        <p className="eyebrow">Upcoming crowd alert</p>
        <h2 id="crowd-alert-title">Busier activity ahead</h2>
        <div className="crowd-alert__level">
          <CrowdBadge level="HIGH" />
          <span>Above your selected preference</span>
        </div>
        <p>
          Near-real-time pedestrian conditions on the route ahead exceed your
          selected crowd tolerance. A lower-stimulation alternative can be
          used when one is available.
        </p>
        {!alternativeAvailable && (
          <p className="crowd-alert__note">
            No lower-crowd alternative is available in this Phase 1 preview.
          </p>
        )}
        <div className="crowd-alert__actions">
          <button
            className="button button--primary"
            disabled={!alternativeAvailable}
            onClick={onStartAlternative}
            type="button"
          >
            Start lower-stimulation route
          </button>
          <button
            className="button button--secondary"
            onClick={onContinue}
            type="button"
          >
            Continue current route
          </button>
        </div>
        <p className="preview-caption">
          Phase 1 state preview — no live crowd re-evaluation has occurred.
        </p>
      </section>
    </div>
  );
}

export default CrowdAlertPanel;
