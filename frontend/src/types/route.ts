export type SensoryLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";

export interface Route {
  id: string;
  name: string;
  distanceKm: number;
  durationMin: number;
  sensoryLevel: SensoryLevel;
  recommended: boolean;
}
