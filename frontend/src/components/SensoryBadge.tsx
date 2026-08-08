import type { SensoryLevel } from "../types/route";

interface SensoryBadgeProps {
  level: SensoryLevel;
}

function SensoryBadge({ level }: SensoryBadgeProps) {
  return <span className={`sensory-badge sensory-${level.toLowerCase()}`}>{level}</span>;
}

export default SensoryBadge;
