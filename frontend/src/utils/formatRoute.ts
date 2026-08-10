export function formatWalkingDistance(distanceMeters: number): string {
  if (distanceMeters < 1000) {
    return `${Math.round(distanceMeters)} m`;
  }
  return `${(distanceMeters / 1000).toFixed(1)} km`;
}

export function formatWalkingDuration(durationSeconds: number): string {
  if (durationSeconds === 0) {
    return "0 min";
  }
  return `${Math.max(1, Math.round(durationSeconds / 60))} min`;
}
