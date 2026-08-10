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
            <span aria-hidden="true">&larr;</span> {backLabel ?? "Back"}
          </Link>
        ) : (
          <Link className="back-link" to={APP_CONFIG.homeRoute}>
            <span aria-hidden="true">&larr;</span> Back to Home
          </Link>
        )}

        <Link className="brand" to={APP_CONFIG.homeRoute} aria-label="CalmWay home">
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
