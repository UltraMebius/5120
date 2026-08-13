import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_CONFIG } from "../config";
import { useJourney } from "../context/JourneyContext";

function ArrivalPage() {
  const navigate = useNavigate();
  const journey = useJourney();
  const [isEnding, setIsEnding] = useState(false);
  const route = journey.selectedRoute;

  if ((!route || !journey.destination) && !isEnding) {
    return <Navigate replace to="/routes/search" />;
  }

  if (!route || !journey.destination) {
    return null;
  }

  function planAnotherWalk() {
    setIsEnding(true);
    journey.resetJourney();
    navigate(APP_CONFIG.homeRoute, { replace: true });
  }

  return (
    <main className="arrival-page">
      <section className="arrival-card">
        <div className="arrival-card__mark" aria-hidden="true">
          &#10003;
        </div>
        <p className="eyebrow">Journey complete</p>
        <h1>You&apos;ve arrived</h1>
        <p className="arrival-card__destination">
          {journey.destination.label}
        </p>
        <p className="arrival-note">
          We hope this route helped make your walk feel a little calmer.
        </p>
        <button
          className="button button--primary button--large button--full"
          onClick={planAnotherWalk}
          type="button"
        >
          Plan another walk
        </button>
      </section>
    </main>
  );
}

export default ArrivalPage;
