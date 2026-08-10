import { Link } from "react-router-dom";

import { APP_CONFIG } from "../config";

const HOME_FEATURES = [
  {
    marker: "01",
    title: "Calmer route choices",
    description:
      "Compare walking routes using pedestrian activity estimates.",
  },
  {
    marker: "02",
    title: "Crowd-aware preferences",
    description:
      "Choose the crowd tolerance that feels right for your journey.",
  },
  {
    marker: "03",
    title: "Route-ahead crowd alerts",
    description:
      "See when available pedestrian data indicates busier activity ahead.",
  },
] as const;

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
            <p className="home-kicker">Calmer walking in Melbourne</p>
            <h1 id="home-title">
              Navigate Melbourne
              <span>with less stress</span>
            </h1>
            <p className="home-hero__description">
              CalmWay helps sensory-sensitive travellers compare walking
              routes using pedestrian activity estimates and choose a crowd
              tolerance that suits their journey.
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
              A calmer route starts with your preference
            </span>
          </div>
        </section>

        <section
          className="home-capabilities"
          aria-labelledby="home-capabilities-title"
        >
          <div className="home-capabilities__heading">
            <p className="home-kicker">Designed around your journey</p>
            <h2 id="home-capabilities-title">What CalmWay helps you do</h2>
          </div>

          <div className="home-feature-grid">
            {HOME_FEATURES.map((feature) => (
              <article className="home-feature-card" key={feature.title}>
                <span className="home-feature-card__marker" aria-hidden="true">
                  {feature.marker}
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>

          <Link
            className="button button--primary button--large home-primary-action"
            to="/routes/search"
          >
            Find a Sensory-Friendly Route
          </Link>
        </section>
      </div>
    </main>
  );
}

export default HomePage;
