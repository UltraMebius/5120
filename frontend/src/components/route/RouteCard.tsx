import CrowdBadge from "../crowd/CrowdBadge";
import type { FrontendCrowdLevel } from "../../types/crowd";
import type { WalkingRoute } from "../../types/route";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../../utils/formatRoute";

interface RouteCardProps {
  isShownOnMap: boolean;
  isRecommended: boolean;
  onDepart: (route: WalkingRoute) => void;
  onShowOnMap: (route: WalkingRoute) => void;
  route: WalkingRoute;
  toleranceLevel: FrontendCrowdLevel;
}

function RouteCard({
  isShownOnMap,
  isRecommended,
  onDepart,
  onShowOnMap,
  route,
  toleranceLevel,
}: RouteCardProps) {
  const crowdResult =
    route.preferenceStatus !== "INSUFFICIENT_DATA" &&
    route.routeCrowdPresentationLevel !== null &&
    route.p75CrowdExposureScore !== null
      ? {
          level: route.routeCrowdPresentationLevel,
        }
      : null;
  const preferenceMessage =
    route.preferenceStatus === "ABOVE_PREFERENCE"
      ? `Above your ${toleranceLevel} preference`
      : `Within your ${toleranceLevel} preference`;

  return (
    <article
      className={`route-card${isShownOnMap ? " route-card--selected" : ""}${
        isRecommended ? " route-card--recommended" : ""
      }`}
    >
      <div className="route-card__topline">
        <div>
          <span className="route-source-label">Walking route</span>
          <h2>{route.name}</h2>
        </div>
        {isRecommended ? (
          <span className="route-recommendation-label">
            CalmWay recommendation
          </span>
        ) : route.rank !== null ? (
          <span className="route-rank-label">Option #{route.rank}</span>
        ) : (
          <span className="crowd-unavailable-label">
            Crowd information unavailable
          </span>
        )}
      </div>

      <div className="route-card__crowd-analysis">
        {crowdResult ? (
          <>
            <CrowdBadge level={crowdResult.level} />
            <span>
              <strong>Current crowd estimate</strong>
              <small
                className={
                  route.preferenceStatus === "ABOVE_PREFERENCE"
                    ? "preference-result preference-result--above"
                    : "preference-result"
                }
              >
                {preferenceMessage}
              </small>
            </span>
          </>
        ) : (
          <span>
            <strong>Crowd information unavailable</strong>
            <small>
              You can still view and use this walking route.
            </small>
          </span>
        )}
      </div>

      <div className="route-card__stats">
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ↔
          </span>
          <span>
            <strong>{formatWalkingDistance(route.distanceMeters)}</strong>
            <small>Walking distance</small>
          </span>
        </div>
        <div>
          <span className="route-stat__icon" aria-hidden="true">
            ◷
          </span>
          <span>
            <strong>{formatWalkingDuration(route.durationSeconds)}</strong>
            <small>Estimated time</small>
          </span>
        </div>
      </div>

      <div className="route-card__actions">
        <button
          aria-pressed={isShownOnMap}
          className="button button--secondary"
          onClick={() => onShowOnMap(route)}
          type="button"
        >
          {isShownOnMap ? "Shown on map" : "View on map"}
        </button>
        <button
          className="button button--primary"
          onClick={() => onDepart(route)}
          type="button"
        >
          Depart
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </article>
  );
}

export default RouteCard;
