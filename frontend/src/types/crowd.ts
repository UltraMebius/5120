export type InternalCrowdLevel =
  | "VERY_LOW"
  | "LOW"
  | "MODERATE"
  | "HIGH"
  | "VERY_HIGH";

export type FrontendCrowdLevel = "LOW" | "MEDIUM" | "HIGH";

export type CrowdPreference =
  | "AVOID_BUSY"
  | "PREFER_QUIETER"
  | "FLEXIBLE";

export type CoverageStatus = "SUPPORTED" | "LIMITED" | "NO_DATA";

export interface CrowdPreferenceOption {
  backendPreference: CrowdPreference;
  description: string;
  maxPreferredNetworkScore: number;
  uiLevel: FrontendCrowdLevel;
}

function readScore(name: string, fallback: number): number {
  const rawValue = import.meta.env[name] as string | undefined;
  const parsedValue = Number(rawValue);

  return rawValue && Number.isFinite(parsedValue) ? parsedValue : fallback;
}

export const CROWD_PREFERENCE_OPTIONS: readonly CrowdPreferenceOption[] = [
  {
    uiLevel: "LOW",
    backendPreference: "AVOID_BUSY",
    maxPreferredNetworkScore: readScore(
      "VITE_AVOID_BUSY_MAX_PREFERRED_SCORE",
      50,
    ),
    description:
      "Prefer quieter routes. Best if you want to avoid busier pedestrian areas.",
  },
  {
    uiLevel: "MEDIUM",
    backendPreference: "PREFER_QUIETER",
    maxPreferredNetworkScore: readScore(
      "VITE_PREFER_QUIETER_MAX_PREFERRED_SCORE",
      75,
    ),
    description:
      "Balanced. Allows moderate pedestrian activity while still preferring quieter routes.",
  },
  {
    uiLevel: "HIGH",
    backendPreference: "FLEXIBLE",
    maxPreferredNetworkScore: readScore(
      "VITE_FLEXIBLE_MAX_PREFERRED_SCORE",
      90,
    ),
    description:
      "More flexible. Allows busier pedestrian areas when needed.",
  },
] as const;

export function toFrontendCrowdLevel(
  level: InternalCrowdLevel,
): FrontendCrowdLevel {
  if (level === "VERY_LOW" || level === "LOW") {
    return "LOW";
  }

  if (level === "MODERATE") {
    return "MEDIUM";
  }

  return "HIGH";
}

export function getPreferenceOption(
  preference: CrowdPreference,
): CrowdPreferenceOption {
  return (
    CROWD_PREFERENCE_OPTIONS.find(
      (option) => option.backendPreference === preference,
    ) ?? CROWD_PREFERENCE_OPTIONS[1]
  );
}
