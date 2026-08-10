import { Link } from "react-router-dom";

function HomeIntegrationPage() {
  return (
    <main className="standalone-state">
      <section className="empty-state" aria-labelledby="navigation-ended-title">
        <h1 id="navigation-ended-title">Navigation ended</h1>
        <p>Your CalmWay route has been cleared.</p>
        <Link className="button button--primary" to="/routes/search">
          Plan another walk
        </Link>
      </section>
    </main>
  );
}

export default HomeIntegrationPage;
