import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";

import {
  MAPBOX_CONFIG,
  isMapboxConfigured,
} from "../../services/mapbox";
import type {
  GeoJsonLineString,
  JourneyLocation,
  MapboxJourneyLocation,
  WalkingRoute,
} from "../../types/route";

const ROUTE_SOURCE_ID = "calmway-walking-route";
const ROUTE_LAYER_ID = "calmway-walking-route-line";
const DEFAULT_CENTER: [longitude: number, latitude: number] = [
  144.9631, -37.8136,
];

type RouteMapVariant = "navigation" | "options";
type RouteCoordinate = [longitude: number, latitude: number];

interface RouteMapProps {
  destination: MapboxJourneyLocation | null;
  origin: JourneyLocation | null;
  route: WalkingRoute;
  variant: RouteMapVariant;
}

interface RouteVisualisation {
  coordinates: RouteCoordinate[];
  destination: RouteCoordinate;
  feature: {
    geometry: GeoJsonLineString;
    properties: Record<string, never>;
    type: "Feature";
  };
  fitKey: string;
  origin: RouteCoordinate;
}

function isValidCoordinate(value: unknown): value is RouteCoordinate {
  if (!Array.isArray(value) || value.length !== 2) {
    return false;
  }

  const [longitude, latitude] = value;
  return (
    typeof longitude === "number" &&
    Number.isFinite(longitude) &&
    longitude >= -180 &&
    longitude <= 180 &&
    typeof latitude === "number" &&
    Number.isFinite(latitude) &&
    latitude >= -90 &&
    latitude <= 90
  );
}

function createVisualisation(
  origin: JourneyLocation | null,
  destination: MapboxJourneyLocation | null,
  route: WalkingRoute,
): RouteVisualisation | null {
  const geometry = route.geometry;
  const originCoordinate: unknown = origin
    ? [origin.longitude, origin.latitude]
    : null;
  const destinationCoordinate: unknown = destination
    ? [destination.longitude, destination.latitude]
    : null;

  if (
    geometry?.type !== "LineString" ||
    !Array.isArray(geometry.coordinates) ||
    geometry.coordinates.length < 2 ||
    !geometry.coordinates.every(isValidCoordinate) ||
    !isValidCoordinate(originCoordinate) ||
    !isValidCoordinate(destinationCoordinate)
  ) {
    return null;
  }

  const coordinates = geometry.coordinates;
  return {
    coordinates,
    destination: destinationCoordinate,
    feature: {
      geometry: {
        coordinates,
        type: "LineString",
      },
      properties: {},
      type: "Feature",
    },
    fitKey: [route.id, ...coordinates.flat(), ...originCoordinate, ...destinationCoordinate].join(
      "|",
    ),
    origin: originCoordinate,
  };
}

function createMarkerElement(
  kind: "destination" | "origin",
  locationName: string,
): HTMLDivElement {
  const element = document.createElement("div");
  element.className = `route-map__marker route-map__marker--${kind}`;
  element.setAttribute("aria-label", `${kind === "origin" ? "Starting point" : "Destination"}: ${locationName}`);
  element.setAttribute("role", "img");
  const label = document.createElement("span");
  label.textContent = kind === "origin" ? "A" : "B";
  element.append(label);
  return element;
}

function RouteMap({ destination, origin, route, variant }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const originMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const destinationMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const lastFittedRouteRef = useRef<string | null>(null);
  const styleReadyRef = useRef(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [styleRevision, setStyleRevision] = useState(0);
  const configured = isMapboxConfigured();
  const visualisation = useMemo(
    () => createVisualisation(origin, destination, route),
    [destination, origin, route],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!configured || !container || mapRef.current) {
      return;
    }

    let map: mapboxgl.Map | null = null;
    const handleMapError = () => {
      setMapError(
        "The route map could not be loaded. Check your connection and try again.",
      );
    };
    const handleStyleLoad = () => {
      styleReadyRef.current = true;
      lastFittedRouteRef.current = null;
      setStyleRevision((revision) => revision + 1);
    };

    try {
      mapboxgl.accessToken = MAPBOX_CONFIG.publicToken;
      map = new mapboxgl.Map({
        center: DEFAULT_CENTER,
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
      map.on("style.load", handleStyleLoad);
    } catch {
      setMapError("The route map could not be initialised in this browser.");
    }

    return () => {
      if (map) {
        map.off("error", handleMapError);
        map.off("style.load", handleStyleLoad);
      }
      originMarkerRef.current?.remove();
      destinationMarkerRef.current?.remove();
      originMarkerRef.current = null;
      destinationMarkerRef.current = null;
      lastFittedRouteRef.current = null;
      styleReadyRef.current = false;
      map?.remove();
      if (mapRef.current === map) {
        mapRef.current = null;
      }
    };
  }, [configured]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current || !visualisation) {
      return;
    }

    try {
      const existingSource = map.getSource(ROUTE_SOURCE_ID) as
        | mapboxgl.GeoJSONSource
        | undefined;

      if (existingSource) {
        existingSource.setData(visualisation.feature);
      } else {
        map.addSource(ROUTE_SOURCE_ID, {
          data: visualisation.feature,
          type: "geojson",
        });
      }

      if (!map.getLayer(ROUTE_LAYER_ID)) {
        map.addLayer({
          id: ROUTE_LAYER_ID,
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          paint: {
            "line-color": "#286c5b",
            "line-opacity": 0.94,
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10,
              4,
              16,
              8,
            ],
          },
          source: ROUTE_SOURCE_ID,
          type: "line",
        });
      }

      if (!originMarkerRef.current) {
        originMarkerRef.current = new mapboxgl.Marker({
          element: createMarkerElement("origin", origin?.name ?? "Origin"),
        })
          .setLngLat(visualisation.origin)
          .addTo(map);
      }
      originMarkerRef.current.setLngLat(visualisation.origin);
      originMarkerRef.current
        .getElement()
        .setAttribute("aria-label", `Starting point: ${origin?.name ?? "Origin"}`);

      if (!destinationMarkerRef.current) {
        destinationMarkerRef.current = new mapboxgl.Marker({
          anchor: "bottom",
          element: createMarkerElement(
            "destination",
            destination?.name ?? "Destination",
          ),
        })
          .setLngLat(visualisation.destination)
          .addTo(map);
      }
      destinationMarkerRef.current.setLngLat(visualisation.destination);
      destinationMarkerRef.current
        .getElement()
        .setAttribute(
          "aria-label",
          `Destination: ${destination?.name ?? "Destination"}`,
        );

      if (lastFittedRouteRef.current !== visualisation.fitKey) {
        const boundsCoordinates = [
          ...visualisation.coordinates,
          visualisation.origin,
          visualisation.destination,
        ];
        const bounds = boundsCoordinates.reduce(
          (currentBounds, coordinate) => currentBounds.extend(coordinate),
          new mapboxgl.LngLatBounds(
            boundsCoordinates[0],
            boundsCoordinates[0],
          ),
        );
        const containerWidth = containerRef.current?.clientWidth ?? 0;
        const padding =
          variant === "navigation"
            ? containerWidth < 640
              ? { bottom: 230, left: 42, right: 42, top: 185 }
              : { bottom: 260, left: 80, right: 80, top: 200 }
            : containerWidth < 640
              ? 42
              : 58;

        map.resize();
        map.fitBounds(bounds, {
          duration: 0,
          maxZoom: 16,
          padding,
        });
        lastFittedRouteRef.current = visualisation.fitKey;
      }

      setMapError(null);
    } catch {
      setMapError("The selected route could not be drawn on the map.");
    }
  }, [destination, origin, styleRevision, variant, visualisation]);

  const fallbackMessage = !configured
    ? "The route map is currently unavailable."
    : !visualisation
      ? "This route cannot currently be displayed on the map. Route details remain available."
      : mapError;

  return (
    <section
      aria-label={
        variant === "navigation"
          ? `Selected walking route map: ${route.name}`
          : `Map showing ${route.name}`
      }
      className={`route-map route-map--${variant}`}
    >
      <div className="route-map__canvas" ref={containerRef} />

      {fallbackMessage && (
        <div className="route-map__message" role="status">
          <strong>Route map unavailable</strong>
          <span>{fallbackMessage}</span>
        </div>
      )}
    </section>
  );
}

export default RouteMap;
