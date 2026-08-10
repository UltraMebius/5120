import CrowdBadge from "../crowd/CrowdBadge";
import type { FrontendCrowdLevel } from "../../types/crowd";
import type { WalkingRoute } from "../../types/route";
import {
  formatWalkingDistance,
  formatWalkingDuration,
} from "../../utils/formatRoute";

interface RouteCardProps {
  isPreviewed: boolean;
  isRecommended: boolean;
  onDepart: (route: WalkingRoute) => void;
  onPreview: (route: WalkingRoute) => void;
  route: WalkingRoute;
  toleranceLevel: FrontendCrowdLevel;
}

function RouteCard({
  isPreviewed,
  isRecommended,
  onDepart,
  onPreview,
  route,
  toleranceLevel,
}: RouteCardProps) {
  const crowdResult =
    route.preferenceStatus !== "INSUFFICIENT_DATA" &&
    route.routeCrowdPresentationLevel !== null &&
    route.p75CrowdExposureScore !== null
      ? {
          level: route.routeCrowdPresentationLevel,
          score: route.p75CrowdExposureScore,
        }
      : null;
  const preferenceMessage =
    route.preferenceStatus === "ABOVE_PREFERENCE"
      ? `Above your ${toleranceLevel} preference`
      : `Within your ${toleranceLevel} preference`;

  return (
    <article
      className={`route-card${isPreviewed ? " route-card--previewed" : ""}${
        isRecommended ? " route-card--recommended" : ""
      }`}
    >
      <div className="route-card__topline">
        <div>
          <span className="route-source-label">Mapbox walking</span>
          <h2>{route.name}</h2>
        </div>
        {isRecommended ? (
          <span className="route-recommendation-label">
            CalmWay recommendation
          </span>
        ) : route.rank !== null ? (
          <span className="route-rank-label">CalmWay rank #{route.rank}</span>
        ) : (
          <span className="crowd-unavailable-label">Crowd unavailable</span>
        )}
      </div>

      <div className="route-card__crowd-analysis">
        {crowdResult ? (
          <>
            <CrowdBadge level={crowdResult.level} />
            <span>
              <strong>
                {crowdResult.score.toFixed(1)} / 100 exposure
              </strong>
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
            <strong>Current crowd analysis unavailable</strong>
            <small>
              {route.dataCoveragePct.toFixed(1)}% of this route currently has
              usable crowd data.
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
          aria-pressed={isPreviewed}
          className="button button--secondary"
          onClick={() => onPreview(route)}
          type="button"
        >
          {isPreviewed ? "Shown on map" : "Preview on map"}
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
