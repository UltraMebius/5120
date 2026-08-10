import type { FrontendCrowdLevel } from "../../types/crowd";

interface CrowdBadgeProps {
  level: FrontendCrowdLevel;
  showLabel?: boolean;
}

function CrowdBadge({ level, showLabel = true }: CrowdBadgeProps) {
  return (
    <span className={`crowd-badge crowd-badge--${level.toLowerCase()}`}>
      <span className="crowd-badge__dot" aria-hidden="true" />
      {showLabel && level}
    </span>
  );
}

export default CrowdBadge;
