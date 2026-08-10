import { Link } from "react-router-dom";

import { APP_CONFIG } from "../../config";

interface AppHeaderProps {
  backLabel?: string;
  backTo?: string;
}

function AppHeader({ backLabel, backTo }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header__inner">
        {backTo ? (
          <Link className="back-link" to={backTo}>
            <span aria-hidden="true">←</span> {backLabel ?? "Back"}
          </Link>
        ) : (
          <a className="back-link" href={APP_CONFIG.homeRoute}>
            <span aria-hidden="true">←</span> Back to Home
          </a>
        )}

        <Link className="brand" to="/routes/search" aria-label="CalmWay route search">
          <span className="brand__mark" aria-hidden="true">
            C
          </span>
          <span>CalmWay</span>
        </Link>

        <span className="header-spacer" aria-hidden="true" />
      </div>
    </header>
  );
}

export default AppHeader;
