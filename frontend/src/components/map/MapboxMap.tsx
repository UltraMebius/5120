import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";

import {
  MAPBOX_CONFIG,
  isMapboxConfigured,
} from "../../services/mapbox";

const MELBOURNE_CBD_CENTER: [longitude: number, latitude: number] = [
  144.9631, -37.8136,
];

function MapboxMap() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [initialisationError, setInitialisationError] = useState<string | null>(
    null,
  );
  const configured = isMapboxConfigured();

  useEffect(() => {
    const container = containerRef.current;
    if (!configured || !container || mapRef.current) {
      return;
    }

    let map: mapboxgl.Map | null = null;
    const handleMapError = () => {
      setInitialisationError(
        "The Mapbox basemap could not be loaded. Check the token and network connection.",
      );
    };

    try {
      mapboxgl.accessToken = MAPBOX_CONFIG.publicToken;
      map = new mapboxgl.Map({
        center: MELBOURNE_CBD_CENTER,
        container,
        style: "mapbox://styles/mapbox/standard",
        zoom: 13.5,
      });
      mapRef.current = map;
      map.addControl(
        new mapboxgl.NavigationControl({ showCompass: false }),
        "top-right",
      );

      map.on("error", handleMapError);
    } catch {
      setInitialisationError(
        "The Mapbox basemap could not be initialised in this browser.",
      );
    }

    return () => {
      if (map) {
        map.off("error", handleMapError);
        map.remove();
      }
      if (mapRef.current === map) {
        mapRef.current = null;
      }
    };
  }, [configured]);

  return (
    <section
      aria-label="Interactive Melbourne CBD basemap smoke test"
      className="search-map"
    >
      <div className="search-map__canvas" ref={containerRef} />

      {!configured && (
        <div className="search-map__message" role="status">
          <strong>Mapbox token is not configured.</strong>
          <span>Add VITE_MAPBOX_PUBLIC_TOKEN to frontend/.env.</span>
        </div>
      )}

      {configured && initialisationError && (
        <div className="search-map__message" role="alert">
          <strong>Map unavailable</strong>
          <span>{initialisationError}</span>
        </div>
      )}

      <span className="search-map__label">Interactive Melbourne basemap</span>
    </section>
  );
}

export default MapboxMap;
