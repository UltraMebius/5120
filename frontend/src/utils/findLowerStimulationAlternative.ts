import type { WalkingRoute } from "../types/route";

/**
 * Scan the authoritative backend order for the first existing route that
 * satisfies the Phase 5B-2 lower-stimulation evidence rule.
 */
export function findLowerStimulationAlternative(
  selectedRoute: WalkingRoute,
  backendOrderedRoutes: readonly WalkingRoute[],
): WalkingRoute | null {
  const selectedP75 = selectedRoute.p75CrowdExposureScore;
  if (selectedP75 === null) {
    return null;
  }

  return (
    backendOrderedRoutes.find(
      (candidate) =>
        candidate.id !== selectedRoute.id &&
        candidate.rank !== null &&
        candidate.p75CrowdExposureScore !== null &&
        candidate.preferenceStatus !== "INSUFFICIENT_DATA" &&
        candidate.initialCrowdAlert.decision === "CLEAR" &&
        candidate.p75CrowdExposureScore < selectedP75,
    ) ?? null
  );
}
