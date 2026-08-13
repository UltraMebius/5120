import { Link } from "react-router-dom";

import { APP_CONFIG } from "../config";

function HomePage() {
  return (
    <main className="home-page">
      <header className="home-header">
        <Link
          aria-label="CalmWay home"
          className="home-brand"
          to={APP_CONFIG.homeRoute}
        >
          <span className="home-brand__mark" aria-hidden="true">
            C
          </span>
          <span>CalmWay</span>
        </Link>
      </header>

      <div className="home-shell">
        <section className="home-hero" aria-labelledby="home-title">
          <div className="home-hero__copy">
            <p className="home-kicker">Sensory-friendly walking</p>
            <h1 id="home-title">Find a calmer way through Melbourne</h1>
            <p className="home-hero__description">
              Compare walking routes using recent pedestrian sensor data.
            </p>
            <Link
              className="button button--primary button--large home-primary-action"
              to="/routes/search"
            >
              Find a Sensory-Friendly Route
              <span aria-hidden="true">&rarr;</span>
            </Link>
            <p className="home-hero__support">
              Compare calmer, faster and balanced walking options.
            </p>
          </div>

          <div className="home-route-illustration" aria-hidden="true">
            <svg viewBox="0 0 520 280">
              <path
                className="home-route-illustration__street"
                d="M30 223 C105 165 121 81 207 83 C293 85 304 219 403 190 C453 175 476 127 492 75"
              />
              <path
                className="home-route-illustration__path"
                d="M30 223 C105 165 121 81 207 83 C293 85 304 219 403 190 C453 175 476 127 492 75"
              />
              <circle
                className="home-route-illustration__activity home-route-illustration__activity--one"
                cx="164"
                cy="92"
                r="12"
              />
              <circle
                className="home-route-illustration__activity home-route-illustration__activity--two"
                cx="349"
                cy="199"
                r="9"
              />
              <g className="home-route-illustration__marker">
                <circle cx="30" cy="223" r="22" />
                <text x="30" y="229" textAnchor="middle">
                  A
                </text>
              </g>
              <g className="home-route-illustration__marker home-route-illustration__marker--destination">
                <circle cx="492" cy="75" r="24" />
                <text x="492" y="81" textAnchor="middle">
                  B
                </text>
              </g>
            </svg>
            <span className="home-route-illustration__label">
              Recent pedestrian estimates help compare each route.
            </span>
          </div>
        </section>

        <ul className="home-benefits" aria-label="Route comparison features">
          <li>
            <strong>Calmer</strong>
            <span>Lower pedestrian activity</span>
          </li>
          <li>
            <strong>Faster</strong>
            <span>Shortest walking time</span>
          </li>
          <li>
            <strong>Balanced</strong>
            <span>Time and activity together</span>
          </li>
        </ul>
      </div>
    </main>
  );
}

export default HomePage;
