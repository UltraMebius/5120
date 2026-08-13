import { describe, expect, it } from "vitest";

import { createRouteMapVisualisation } from "../src/components/map/RouteMap";
import { ROUTE_ACTIVITY_COLOURS } from "../src/utils/routeOptionPresentation";
import { makeRouteOptionsResponse, SEARCH_REQUEST } from "./fixtures";

describe("route map data", () => {
  it("uses every full candidate geometry and semantic activity colour", () => {
    const routes = makeRouteOptionsResponse(3).routes;
    const result = createRouteMapVisualisation(
      SEARCH_REQUEST.origin,
      SEARCH_REQUEST.destination,
      routes,
    );

    expect(result?.featureCollection.features).toHaveLength(3);
    expect(result?.featureCollection.features.map((feature) => feature.geometry))
      .toEqual(routes.map((route) => route.geometry));
    expect(
      result?.featureCollection.features.map(
        (feature) => feature.properties.colour,
      ),
    ).toEqual([
      ROUTE_ACTIVITY_COLOURS.LOWEST,
      ROUTE_ACTIVITY_COLOURS.MIDDLE,
      ROUTE_ACTIVITY_COLOURS.HIGHEST,
    ]);
  });

  it("uses neutral grey for unknown pedestrian activity", () => {
    const routes = makeRouteOptionsResponse(1, "UNKNOWN").routes;
    const result = createRouteMapVisualisation(
      SEARCH_REQUEST.origin,
      SEARCH_REQUEST.destination,
      routes,
    );

    expect(result?.featureCollection.features[0].properties.colour).toBe(
      ROUTE_ACTIVITY_COLOURS.UNKNOWN,
    );
  });
});
