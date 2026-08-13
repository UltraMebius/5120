import type {
  ComparisonBasis,
  RelativePedestrianActivity,
} from "../types/routeOptions";

export const ROUTE_ACTIVITY_COLOURS: Record<
  RelativePedestrianActivity,
  string
> = {
  HIGHEST: "#b8403a",
  LOWEST: "#2d795f",
  MIDDLE: "#c56a00",
  UNKNOWN: "#77827e",
};

export function formatPedestrianActivity(
  value: number | null,
  basis: ComparisonBasis,
): string {
  if (basis === "UNKNOWN" || value === null) {
    return "Pedestrian data unavailable";
  }

  return `≈ ${Math.round(value)} movements/min`;
}

export function pedestrianActivityLabel(
  activity: RelativePedestrianActivity,
): string {
  switch (activity) {
    case "LOWEST":
      return "Lowest pedestrian activity";
    case "MIDDLE":
      return "Middle pedestrian activity";
    case "HIGHEST":
      return "Highest pedestrian activity";
    case "UNKNOWN":
      return "Relative pedestrian activity unavailable";
  }
}

export function pedestrianSourceLabel(basis: ComparisonBasis): string {
  switch (basis) {
    case "LIVE":
      return "Recent sensor estimate";
    case "HISTORICAL_ESTIMATE":
      return "Historical estimate";
    case "UNKNOWN":
      return "Pedestrian data unavailable";
  }
}
