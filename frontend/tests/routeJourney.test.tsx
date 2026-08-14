import { useEffect, useState, type ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { JourneyProvider, useJourney } from "../src/context/JourneyContext";
import ArrivalPage from "../src/pages/ArrivalPage";
import NavigationPage from "../src/pages/NavigationPage";
import type { RouteOptionsResponse } from "../src/types/routeOptions";
import {
  makeMultiRoleRouteOptionsResponse,
  makeRouteOptionsResponse,
  SEARCH_REQUEST,
} from "./fixtures";

vi.mock("../src/components/map/RouteMap", () => ({
  default: function MockRouteMap({
    activeRouteId,
    mode,
    routes,
  }: {
    activeRouteId?: string;
    mode: string;
    routes: { geometry: { coordinates: unknown[] }; routeId: string }[];
  }) {
    const activeRoute = routes.find(
      (route) => route.routeId === activeRouteId,
    );
    return (
      <div
        data-active-geometry={JSON.stringify(
          activeRoute?.geometry.coordinates ?? [],
        )}
        data-map-mode={mode}
        data-testid="route-map"
      >
        {mode}:{activeRouteId ?? "none"}:
        {routes.map((route) => route.routeId).join(",")}:
        {routes.map((route) => route.geometry.coordinates.length).join(",")}
      </div>
    );
  },
}));

interface JourneySeedProps {
  children: ReactNode;
  response: RouteOptionsResponse;
  selectedIndex?: number;
}

function JourneySeed({
  children,
  response,
  selectedIndex,
}: JourneySeedProps) {
  const journey = useJourney();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    journey.setRouteOptions(SEARCH_REQUEST, response);
    if (selectedIndex !== undefined) {
      journey.selectRoute(response.routes[selectedIndex]);
    }
    setReady(true);
  }, []);

  return ready ? children : null;
}

function SearchMarker() {
  return <div>Safe search page</div>;
}

function LocationProbe() {
  return <output data-testid="current-path">{useLocation().pathname}</output>;
}

function HomeProbe() {
  const journey = useJourney();
  return (
    <div>
      Home selected {journey.selectedRoute?.routeId ?? "none"}, options{" "}
      {journey.routeOptions.length}
    </div>
  );
}

function renderJourney(
  initialEntry: string,
  response?: RouteOptionsResponse,
  selectedIndex?: number,
) {
  const routedContent = (
    <>
      <Routes>
        <Route path="/routes/search" element={<SearchMarker />} />
        <Route path="/navigation" element={<NavigationPage />} />
        <Route path="/arrival" element={<ArrivalPage />} />
        <Route path="/home" element={<HomeProbe />} />
      </Routes>
      <LocationProbe />
    </>
  );

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <JourneyProvider>
        {response ? (
          <JourneySeed response={response} selectedIndex={selectedIndex}>
            {routedContent}
          </JourneySeed>
        ) : (
          routedContent
        )}
      </JourneyProvider>
    </MemoryRouter>,
  );
}

describe("route selection and active navigation journey", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([1, 2, 3] as const)(
    "renders %i backend route option(s) in order and passes every geometry to the map",
    async (routeCount) => {
      renderJourney(
        "/navigation",
        makeRouteOptionsResponse(routeCount),
      );

      expect(await screen.findAllByRole("article")).toHaveLength(routeCount);
      expect(screen.getAllByRole("tab")).toHaveLength(routeCount);
      expect(
        screen.getByRole("heading", { name: "Choose your walk" }),
      ).toBeInTheDocument();
      const map = screen.getByTestId("route-map");
      expect(map).toHaveAttribute("data-map-mode", "selection");
      expect(map).toHaveTextContent(
        Array.from({ length: routeCount }, (_, index) => `route-${index + 1}`).join(
          ",",
        ),
      );
      expect(map).toHaveTextContent(
        Array.from({ length: routeCount }, () => "3").join(","),
      );
    },
  );

  it("shows multiple backend roles, rounded movements, and live source metadata", async () => {
    const response = makeRouteOptionsResponse(1, "LIVE");
    response.routes[0].roleBadges = ["CALMEST", "FASTEST"];
    renderJourney("/navigation", response);

    expect(await screen.findByText("CALMEST")).toBeInTheDocument();
    expect(screen.getByText("FASTEST")).toBeInTheDocument();
    expect(screen.getAllByText("≈ 8 movements/min").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Recent sensor estimate").length,
    ).toBeGreaterThan(0);
  });

  it("reselects one multi-role route by ID without duplicating its card or Navigation data", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    const response = makeMultiRoleRouteOptionsResponse();
    const multiRoleRoute = response.routes[0];
    const fetchMock = vi.mocked(fetch);

    renderJourney("/navigation", response);

    const articles = await screen.findAllByRole("article");
    expect(articles).toHaveLength(3);
    expect(within(articles[0]).getByText("CALMEST")).toBeInTheDocument();
    expect(within(articles[0]).getByText("FASTEST")).toBeInTheDocument();
    expect(within(articles[1]).getByText("BALANCED")).toBeInTheDocument();
    expect(within(articles[2]).getByText("Route 3")).toBeInTheDocument();

    const selectors = screen.getAllByRole("tab");
    await userEvent.click(selectors[1]);
    expect(screen.getByTestId("route-map")).toHaveTextContent(
      `selection:${response.routes[1].routeId}`,
    );
    await userEvent.click(selectors[0]);
    const map = screen.getByTestId("route-map");
    expect(map).toHaveTextContent(`selection:${multiRoleRoute.routeId}`);
    expect(map).toHaveAttribute(
      "data-active-geometry",
      JSON.stringify(multiRoleRoute.geometry.coordinates),
    );

    await userEvent.click(
      screen.getByRole("button", {
        name: "Select CALMEST + FASTEST route",
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("navigation-page")).toHaveAttribute(
        "data-navigation-mode",
        "active",
      ),
    );

    expect(map).toHaveTextContent(`active:${multiRoleRoute.routeId}`);
    expect(map).toHaveAttribute(
      "data-active-geometry",
      JSON.stringify(multiRoleRoute.geometry.coordinates),
    );
    expect(
      within(
        screen.getByRole("region", { name: "Next walking direction" }),
      ).getByText(multiRoleRoute.steps[0].instruction),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Route summary" })).getByText(
        "CALMEST + FASTEST",
      ),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Back to route selection" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("navigation-page")).toHaveAttribute(
        "data-navigation-mode",
        "selection",
      ),
    );

    const reselectionTabs = screen.getAllByRole("tab");
    await userEvent.click(reselectionTabs[1]);
    await userEvent.click(reselectionTabs[0]);
    expect(map).toHaveTextContent(`selection:${multiRoleRoute.routeId}`);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Select CALMEST + FASTEST route",
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("navigation-page")).toHaveAttribute(
        "data-navigation-mode",
        "active",
      ),
    );

    expect(map).toHaveTextContent(`active:${multiRoleRoute.routeId}`);
    expect(map).toHaveAttribute(
      "data-active-geometry",
      JSON.stringify(multiRoleRoute.geometry.coordinates),
    );
    expect(
      within(
        screen.getByRole("region", { name: "Next walking direction" }),
      ).getByText(multiRoleRoute.steps[0].instruction),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("distinguishes historical evidence from unavailable/null activity", async () => {
    const { unmount } = renderJourney(
      "/navigation",
      makeRouteOptionsResponse(1, "HISTORICAL_ESTIMATE"),
    );
    expect(
      await screen.findAllByText("Historical estimate"),
    ).not.toHaveLength(0);
    expect(
      screen.queryByText("Recent sensor estimate"),
    ).not.toBeInTheDocument();
    unmount();

    renderJourney(
      "/navigation",
      makeRouteOptionsResponse(1, "UNKNOWN"),
    );
    expect(
      (await screen.findAllByText("Pedestrian data unavailable")).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/≈ 0 movements\/min/)).not.toBeInTheDocument();
  });

  it("confirms route B, activates its navigation details, and makes no request", async () => {
    const response = makeRouteOptionsResponse(2);
    const fetchMock = vi.mocked(fetch);
    renderJourney("/navigation", response);

    const selectors = await screen.findAllByRole("tab");
    await userEvent.click(selectors[1]);
    const map = screen.getByTestId("route-map");
    const selectionPanel = screen.getByTestId("route-selection-panel");
    expect(map).toHaveTextContent(
      "selection:route-2:route-1,route-2",
    );
    expect(
      screen.getByRole("heading", { name: "Choose your walk" }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /select fastest route/i }),
    );

    expect(screen.getByTestId("navigation-page")).toHaveAttribute(
      "data-navigation-mode",
      "transition-to-active",
    );
    expect(selectionPanel).toBeInTheDocument();
    expect(selectionPanel).toHaveAttribute("aria-hidden", "true");
    await waitFor(
      () =>
        expect(screen.getByTestId("navigation-page")).toHaveAttribute(
          "data-navigation-mode",
          "active",
        ),
      { timeout: 1500 },
    );
    expect(
      screen.getByText("Instruction for route 2"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("route-map")).toBe(map);
    expect(map).toHaveAttribute("data-map-mode", "active");
    expect(map).toHaveTextContent(
      "active:route-2:route-1,route-2:3,3",
    );
    expect(
      screen.queryByRole("heading", { name: "Choose your walk" }),
    ).not.toBeInTheDocument();
    expect(selectionPanel).toBeInTheDocument();
    expect(screen.getByText("Route guidance")).toBeInTheDocument();
    const routeSummary = screen.getByRole("region", {
      name: "Route summary",
    });
    expect(within(routeSummary).getByText("14 min")).toBeInTheDocument();
    expect(within(routeSummary).getByText("1.2 km")).toBeInTheDocument();
    expect(within(routeSummary).getByText("FASTEST")).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent(
      "/navigation",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns from active navigation to selection without leaving /navigation", async () => {
    renderJourney("/navigation", makeRouteOptionsResponse(2), 1);

    const map = screen.getByTestId("route-map");
    const selectionPanel = screen.getByTestId("route-selection-panel");
    expect(map).toHaveAttribute("data-map-mode", "active");

    await userEvent.click(
      screen.getByRole("button", { name: "Back to route selection" }),
    );

    expect(screen.getByTestId("navigation-page")).toHaveAttribute(
      "data-navigation-mode",
      "transition-to-selection",
    );
    expect(selectionPanel).toBeInTheDocument();
    expect(selectionPanel).toHaveAttribute("aria-hidden", "true");
    await waitFor(
      () =>
        expect(screen.getByTestId("navigation-page")).toHaveAttribute(
          "data-navigation-mode",
          "selection",
        ),
      { timeout: 1500 },
    );

    expect(screen.getByTestId("route-map")).toBe(map);
    expect(map).toHaveAttribute("data-map-mode", "selection");
    expect(map).toHaveTextContent("route-1,route-2");
    expect(selectionPanel).toHaveAttribute("aria-hidden", "false");
    expect(screen.getAllByRole("tab")[1]).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("current-path")).toHaveTextContent(
      "/navigation",
    );
  });

  it("Edit search returns to Search without fetching", async () => {
    const response = makeRouteOptionsResponse(2);
    const fetchMock = vi.mocked(fetch);
    renderJourney("/navigation", response);

    await userEvent.click(
      await screen.findByRole("button", { name: "Edit search" }),
    );

    expect(await screen.findByText("Safe search page")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses a safe maneuver fallback when the selected route has no steps", async () => {
    const response = makeRouteOptionsResponse(1);
    response.routes[0].steps = [];
    renderJourney("/navigation", response, 0);

    expect(
      await screen.findByText("Continue along the selected route"),
    ).toBeInTheDocument();
  });

  it("Exit resets the journey and returns Home", async () => {
    renderJourney("/navigation", makeRouteOptionsResponse(2), 0);

    await userEvent.click(
      await screen.findByRole("button", { name: "Exit navigation" }),
    );

    expect(
      await screen.findByText("Home selected none, options 0"),
    ).toBeInTheDocument();
  });

  it("keeps all three semantic route selectors discoverable", async () => {
    renderJourney("/navigation", makeRouteOptionsResponse(3));

    const articles = await screen.findAllByRole("article");
    expect(articles).toHaveLength(3);
    expect(articles[0]).toHaveAttribute("data-activity", "LOWEST");
    expect(articles[0]).toHaveClass("route-card--activity-lowest");
    expect(articles[0]).toHaveTextContent("CALMEST");
    expect(articles[0]).toHaveTextContent("≈ 8 movements/min");
    expect(articles[0]).toHaveTextContent("Lowest pedestrian activity");

    expect(articles[1]).toHaveAttribute("data-activity", "MIDDLE");
    expect(articles[1]).toHaveClass("route-card--activity-middle");
    expect(articles[1]).toHaveTextContent("BALANCED");
    expect(articles[1]).toHaveTextContent("≈ 11 movements/min");
    expect(articles[1]).toHaveTextContent("Middle pedestrian activity");

    expect(articles[2]).toHaveAttribute("data-activity", "HIGHEST");
    expect(articles[2]).toHaveClass("route-card--activity-highest");
    expect(articles[2]).toHaveTextContent("FASTEST");
    expect(articles[2]).toHaveTextContent("≈ 15 movements/min");
    expect(articles[2]).toHaveTextContent("Highest pedestrian activity");
    expect(screen.getByRole("tablist")).toHaveClass("route-list--count-3");
    expect(screen.getByRole("button", { name: /select calmest route/i })).toBeVisible();
    expect(
      screen.getByLabelText("About movements per minute"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Estimated pedestrian movements per minute along the route, based on nearby sensors.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps role classifications consistent with displayed activity and duration", async () => {
    const routes = makeRouteOptionsResponse(3).routes;
    const calmest = routes.find((route) => route.roleBadges.includes("CALMEST"))!;
    const balanced = routes.find((route) =>
      route.roleBadges.includes("BALANCED"),
    )!;
    const fastest = routes.find((route) => route.roleBadges.includes("FASTEST"))!;

    expect(calmest.typicalPedestrianMovementsPerMinute!).toBeLessThanOrEqual(
      balanced.typicalPedestrianMovementsPerMinute!,
    );
    expect(calmest.typicalPedestrianMovementsPerMinute!).toBeLessThanOrEqual(
      fastest.typicalPedestrianMovementsPerMinute!,
    );
    expect(fastest.durationSeconds).toBe(
      Math.min(...routes.map((route) => route.durationSeconds)),
    );
  });

  it.each([
    ["CALMEST", 0],
    ["BALANCED", 1],
    ["FASTEST", 2],
  ] as const)(
    "selecting the %s card preserves its route ID, geometry, and navigation details",
    async (role, routeIndex) => {
      vi.stubGlobal(
        "matchMedia",
        vi.fn(() => ({ matches: true })),
      );
      const response = makeRouteOptionsResponse(3);
      const selectedRoute = response.routes[routeIndex];
      renderJourney("/navigation", response);

      await userEvent.click((await screen.findAllByRole("tab"))[routeIndex]);
      const map = screen.getByTestId("route-map");
      expect(map).toHaveTextContent(`selection:${selectedRoute.routeId}`);
      expect(map).toHaveAttribute(
        "data-active-geometry",
        JSON.stringify(selectedRoute.geometry.coordinates),
      );

      await userEvent.click(
        screen.getByRole("button", {
          name: new RegExp(`select ${role.toLowerCase()} route`, "i"),
        }),
      );
      await waitFor(() =>
        expect(screen.getByTestId("navigation-page")).toHaveAttribute(
          "data-navigation-mode",
          "active",
        ),
      );

      expect(map).toHaveTextContent(`active:${selectedRoute.routeId}`);
      expect(map).toHaveAttribute(
        "data-active-geometry",
        JSON.stringify(selectedRoute.geometry.coordinates),
      );
      expect(
        within(
          screen.getByRole("region", { name: "Next walking direction" }),
        ).getByText(selectedRoute.steps[0].instruction),
      ).toBeInTheDocument();
      expect(
        within(screen.getByRole("region", { name: "Route summary" })).getByText(
          role,
        ),
      ).toBeInTheDocument();
    },
  );

  it("changes active route details from each selector without fetching", async () => {
    const fetchMock = vi.mocked(fetch);
    renderJourney("/navigation", makeRouteOptionsResponse(3));

    const selectors = await screen.findAllByRole("tab");
    const activeDetail = screen.getByRole("tabpanel");
    expect(selectors[0]).toHaveAttribute("aria-selected", "true");
    expect(within(activeDetail).getByText("≈ 8 movements/min")).toBeInTheDocument();

    await userEvent.click(selectors[1]);
    expect(selectors[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("route-map")).toHaveTextContent(
      "selection:route-2:route-1,route-2,route-3",
    );
    expect(within(activeDetail).getByText("BALANCED")).toBeInTheDocument();
    expect(within(activeDetail).getByText("≈ 11 movements/min")).toBeInTheDocument();

    await userEvent.click(selectors[2]);
    expect(selectors[2]).toHaveAttribute("aria-selected", "true");
    expect(within(activeDetail).getByText("FASTEST")).toBeInTheDocument();
    expect(within(activeDetail).getByText("≈ 15 movements/min")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves explicit zero while keeping missing activity unavailable", async () => {
    const zeroResponse = makeRouteOptionsResponse(1, "LIVE");
    zeroResponse.routes[0].typicalPedestrianMovementsPerMinute = 0;
    const { unmount } = renderJourney("/navigation", zeroResponse);
    expect(
      (await screen.findAllByText("≈ 0 movements/min")).length,
    ).toBeGreaterThan(0);
    unmount();

    renderJourney("/navigation", makeRouteOptionsResponse(1, "UNKNOWN"));
    expect(
      await screen.findAllByText("Pedestrian data unavailable"),
    ).not.toHaveLength(0);
    expect(screen.queryByText("≈ 0 movements/min")).not.toBeInTheDocument();
  });

  it("completes the selected journey and starts another walk", async () => {
    renderJourney("/navigation", makeRouteOptionsResponse(1), 0);

    await userEvent.click(
      await screen.findByRole("button", { name: "Finish route" }),
    );
    expect(await screen.findByRole("heading", { name: "You've arrived" })).toBeInTheDocument();
    expect(screen.getByText(SEARCH_REQUEST.destination.label)).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Plan another walk" }),
    );
    expect(
      await screen.findByText("Home selected none, options 0"),
    ).toBeInTheDocument();
  });

  it.each(["/navigation", "/arrival"])(
    "redirects unsafe direct access to %s back to Search",
    async (path) => {
      renderJourney(path);

      expect(await screen.findByText("Safe search page")).toBeInTheDocument();
    },
  );
});
