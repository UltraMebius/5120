import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchRouteOptions, RouteOptionsApiError } from "../src/services/api";
import {
  makeRouteOptionsResponse,
  SEARCH_REQUEST,
} from "./fixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("fetchRouteOptions", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts only origin and destination coordinates to the route-options endpoint", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(makeRouteOptionsResponse(1)));
    vi.stubGlobal("fetch", fetchMock);

    await fetchRouteOptions(SEARCH_REQUEST);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/routes\/options$/);
    expect(init?.method).toBe("POST");
    const requestBody = JSON.parse(String(init?.body)) as Record<
      string,
      unknown
    >;
    expect(requestBody).toEqual({
      destination: {
        latitude: SEARCH_REQUEST.destination.latitude,
        longitude: SEARCH_REQUEST.destination.longitude,
      },
      origin: {
        latitude: SEARCH_REQUEST.origin.latitude,
        longitude: SEARCH_REQUEST.origin.longitude,
      },
    });
    expect(requestBody).not.toHaveProperty("preference");
    expect(String(init?.body)).not.toMatch(/LOW|MEDIUM|HIGH|threshold/);
  });

  it.each([
    [1, "LIVE"],
    [2, "HISTORICAL_ESTIMATE"],
    [3, "UNKNOWN"],
  ] as const)(
    "parses %i route(s) using %s evidence",
    async (routeCount, comparisonBasis) => {
      const response = makeRouteOptionsResponse(routeCount, comparisonBasis);
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response)),
      );

      const result = await fetchRouteOptions(SEARCH_REQUEST);

      expect(result.comparisonBasis).toBe(comparisonBasis);
      expect(result.routes).toHaveLength(routeCount);
      expect(result.routes[0].roleBadges).toEqual(["CALMEST", "FASTEST"]);
      expect(result.routes[0].geometry).toEqual(response.routes[0].geometry);
    },
  );

  it("preserves numeric zero and nullable pedestrian values as different values", async () => {
    const response = makeRouteOptionsResponse(2, "LIVE");
    response.routes[0].typicalPedestrianMovementsPerMinute = 0;
    response.routes[0].comparisonPedestrianFlow.typicalMovementsPerMinute = 0;
    response.routes[1].typicalPedestrianMovementsPerMinute = null;
    response.routes[1].comparisonPedestrianFlow.typicalMovementsPerMinute = null;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response)),
    );

    const result = await fetchRouteOptions(SEARCH_REQUEST);

    expect(result.routes[0].typicalPedestrianMovementsPerMinute).toBe(0);
    expect(result.routes[1].typicalPedestrianMovementsPerMinute).toBeNull();
  });

  it("rejects malformed flow evidence with a safe API error", async () => {
    const response = makeRouteOptionsResponse(1);
    response.routes[0].comparisonPedestrianFlow.coveragePct = 101;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response)),
    );

    await expect(fetchRouteOptions(SEARCH_REQUEST)).rejects.toMatchObject({
      reason: "OPTIONS_UNAVAILABLE",
    } satisfies Partial<RouteOptionsApiError>);
  });
});
