import type { FrontendCrowdLevel } from "../../types/crowd";
import type { InitialCrowdAlert, WalkingRoute } from "../../types/route";

interface CrowdAlertPanelProps {
  alert: InitialCrowdAlert;
  alternative: WalkingRoute | null;
  onContinue: () => void;
  onStartAlternative: () => void;
  toleranceLevel: FrontendCrowdLevel;
}

function CrowdAlertPanel({
  alert,
  alternative,
  onContinue,
  onStartAlternative,
  toleranceLevel,
}: CrowdAlertPanelProps) {
  const triggerRange =
    alert.triggerStartDistanceMeters !== null &&
    alert.triggerEndDistanceMeters !== null
      ? `${Math.round(alert.triggerStartDistanceMeters)}–${Math.round(
          alert.triggerEndDistanceMeters,
        )} m from this route's start`
      : null;

  return (
    <section
      aria-labelledby="crowd-alert-title"
      className="crowd-alert"
      role="alert"
    >
      <div className="crowd-alert__heading">
        <div className="crowd-alert__icon" aria-hidden="true">
          !
        </div>
        <div>
          <p className="eyebrow">Initial route-ahead crowd check</p>
          <h2 id="crowd-alert-title">Busier pedestrian activity ahead</h2>
        </div>
      </div>
      <p>
        CalmWay detected sustained pedestrian activity above your selected
        crowd preference within the next{" "}
        {Math.round(alert.lookAheadDistanceMeters)} m.
      </p>
      <p className="crowd-alert__detail">
        Crowd activity is above your {toleranceLevel} preference ahead.
        {triggerRange && <> Detected approximately {triggerRange}.</>}
      </p>
      {!alternative && (
        <p className="crowd-alert__note">
          No qualifying lower-stimulation alternative is available among the
          routes already returned for this search.
        </p>
      )}
      <div className="crowd-alert__actions">
        {alternative && (
          <button
            className="button button--primary"
            onClick={onStartAlternative}
            type="button"
          >
            Start lower-stimulation route
          </button>
        )}
        <button
          className="button button--secondary"
          onClick={onContinue}
          type="button"
        >
          Continue current route
        </button>
      </div>
      <p className="preview-caption">
        This is an initial check at 0 m route progress. It does not track live
        location or update while you walk.
      </p>
    </section>
  );
}

export default CrowdAlertPanel;
