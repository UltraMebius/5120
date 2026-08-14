import type {
  ComparisonBasis,
  RouteOption,
  RouteOptionsResponse,
  RouteOptionsSearchRequest,
} from "../src/types/routeOptions";

export const SEARCH_REQUEST: RouteOptionsSearchRequest = {
  destination: {
    fullAddress: "Flinders Street Railway Station, Melbourne VIC",
    label: "Flinders Street Railway Station",
    latitude: -37.8183,
    longitude: 144.9671,
    mapboxId: "destination-mapbox-id",
    name: "Flinders Street Railway Station",
    source: "MAPBOX",
  },
  origin: {
    fullAddress: "Melbourne Central, Melbourne VIC",
    label: "Melbourne Central",
    latitude: -37.8102,
    longitude: 144.9628,
    mapboxId: "origin-mapbox-id",
    name: "Melbourne Central",
    source: "MAPBOX",
  },
};

export function makeRouteOption(
  index: number,
  comparisonBasis: ComparisonBasis = "LIVE",
): RouteOption {
  const typicalValues = [8, 11, 15] as const;
  const typical =
    comparisonBasis === "UNKNOWN" ? null : (typicalValues[index] ?? 11);
  const relativeActivities = ["LOWEST", "MIDDLE", "HIGHEST"] as const;
  const roleBadges: RouteOption["roleBadges"] =
    index === 0
      ? ["CALMEST"]
      : index === 1
        ? ["BALANCED"]
        : ["FASTEST"];

  return {
    balancedScore: index === 1 ? 0.42 : null,
    candidateSource:
      index === 0
        ? "DIRECT"
        : index === 1
          ? "MAPBOX_ALTERNATIVE"
          : "FLOW_WAYPOINT",
    comparisonPedestrianFlow: {
      basis: comparisonBasis,
      coveragePct: comparisonBasis === "UNKNOWN" ? null : 80,
      maximumMovementsPerMinute:
        comparisonBasis === "UNKNOWN" ? null : (typical as number) + 7,
      p75MovementsPerMinute:
        comparisonBasis === "UNKNOWN" ? null : (typical as number) + 4,
      typicalMovementsPerMinute: typical,
    },
    distanceMeters: 1000 + index * 220,
    durationSeconds: 960 - index * 120,
    geometry: {
      coordinates: [
        [144.9628, -37.8102],
        [144.964 + index * 0.001, -37.814 - index * 0.001],
        [144.9671, -37.8183],
      ],
      type: "LineString",
    },
    historicalPedestrianFlow: {
      coveragePct: comparisonBasis === "UNKNOWN" ? 0 : 100,
      maximumMovementsPerMinute:
        comparisonBasis === "UNKNOWN" ? null : (typical as number) + 9,
      medianMovementsPerMinute:
        comparisonBasis === "UNKNOWN" ? null : typical,
      p75MovementsPerMinute:
        comparisonBasis === "UNKNOWN" ? null : (typical as number) + 5,
    },
    livePedestrianFlow: {
      coveragePct: comparisonBasis === "LIVE" ? 80 : 0,
      maximumMovementsPerMinute:
        comparisonBasis === "LIVE" ? (typical as number) + 7 : null,
      medianMovementsPerMinute: comparisonBasis === "LIVE" ? typical : null,
      p75MovementsPerMinute:
        comparisonBasis === "LIVE" ? (typical as number) + 4 : null,
    },
    relativePedestrianActivity:
      comparisonBasis === "UNKNOWN"
        ? "UNKNOWN"
        : relativeActivities[index] ?? "MIDDLE",
    roleBadges,
    routeId: `route-${index + 1}`,
    routeIndex: index,
    steps: [
      {
        distanceMeters: 120 + index,
        durationSeconds: 90,
        instruction: `Instruction for route ${index + 1}`,
        maneuverLocation: [144.9635, -37.812],
      },
    ],
    typicalPedestrianMovementsPerMinute: typical,
  };
}

export function makeRouteOptionsResponse(
  routeCount: 1 | 2 | 3,
  comparisonBasis: ComparisonBasis = "LIVE",
): RouteOptionsResponse {
  const routes = Array.from({ length: routeCount }, (_, index) =>
    makeRouteOption(index, comparisonBasis),
  );

  if (routeCount === 1) {
    routes[0].roleBadges = ["FASTEST"];
    routes[0].relativePedestrianActivity = "UNKNOWN";
    routes[0].balancedScore = null;
  }

  if (routeCount === 2 && comparisonBasis !== "UNKNOWN") {
    routes[0].roleBadges = ["CALMEST"];
    routes[0].balancedScore = null;
    routes[1].roleBadges = ["FASTEST"];
    routes[1].balancedScore = null;
    routes[1].relativePedestrianActivity = "HIGHEST";
  }

  return {
    comparisonBasis,
    generationReason:
      routeCount === 1
        ? "ONLY_ONE_MEANINGFUL_CORRIDOR"
        : routeCount === 2
          ? "MULTIPLE_MAPBOX_ROUTES"
          : "WAYPOINT_ALTERNATIVE_ADDED",
    routes,
  };
}

export function makeMultiRoleRouteOptionsResponse(): RouteOptionsResponse {
  const response = makeRouteOptionsResponse(3, "LIVE");
  const [routeA, routeB, routeC] = response.routes;

  routeA.durationSeconds = 780;
  routeA.roleBadges = ["CALMEST", "FASTEST"];
  routeA.balancedScore = 0.35;
  routeB.durationSeconds = 1_080;
  routeB.roleBadges = ["BALANCED"];
  routeB.balancedScore = 0.4;
  routeC.durationSeconds = 1_320;
  routeC.roleBadges = [];
  routeC.balancedScore = 0.8;

  return response;
}
