import { useEffect, useState, type ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { JourneyProvider, useJourney } from "../src/context/JourneyContext";
import ArrivalPage from "../src/pages/ArrivalPage";
import NavigationPage from "../src/pages/NavigationPage";
import RouteOptionsPage from "../src/pages/RouteOptionsPage";
import type { RouteOptionsResponse } from "../src/types/routeOptions";
import { makeRouteOptionsResponse, SEARCH_REQUEST } from "./fixtures";

vi.mock("../src/components/map/RouteMap", () => ({
  default: ({
    routes,
    variant,
  }: {
    routes: { geometry: { coordinates: unknown[] }; routeId: string }[];
    variant: string;
  }) => (
    <div data-testid={`route-map-${variant}`}>
      {variant}:{routes.map((route) => route.routeId).join(",")}:
      {routes.map((route) => route.geometry.coordinates.length).join(",")}
    </div>
  ),
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
    <Routes>
      <Route path="/routes/search" element={<SearchMarker />} />
      <Route path="/routes/options" element={<RouteOptionsPage />} />
      <Route path="/navigation" element={<NavigationPage />} />
      <Route path="/arrival" element={<ArrivalPage />} />
      <Route path="/home" element={<HomeProbe />} />
    </Routes>
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

describe("route options and navigation journey", () => {
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
        "/routes/options",
        makeRouteOptionsResponse(routeCount),
      );

      expect(await screen.findAllByRole("article")).toHaveLength(routeCount);
      expect(screen.getAllByRole("tab")).toHaveLength(routeCount);
      const map = screen.getByTestId("route-map-options");
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
    renderJourney("/routes/options", response);

    expect(await screen.findByText("CALMEST")).toBeInTheDocument();
    expect(screen.getByText("FASTEST")).toBeInTheDocument();
    expect(screen.getAllByText("≈ 8 movements/min").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Recent sensor estimate").length,
    ).toBeGreaterThan(0);
  });

  it("distinguishes historical evidence from unavailable/null activity", async () => {
    const { unmount } = renderJourney(
      "/routes/options",
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
      "/routes/options",
      makeRouteOptionsResponse(1, "UNKNOWN"),
    );
    expect(
      (await screen.findAllByText("Pedestrian data unavailable")).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/≈ 0 movements\/min/)).not.toBeInTheDocument();
  });

  it("selects route B, renders only B in Navigation, and makes no request", async () => {
    const response = makeRouteOptionsResponse(2);
    const fetchMock = vi.mocked(fetch);
    renderJourney("/routes/options", response);

    const selectors = await screen.findAllByRole("tab");
    await userEvent.click(selectors[1]);
    await userEvent.click(
      screen.getByRole("button", { name: /select balanced route/i }),
    );

    expect(
      await screen.findByText("Instruction for route 2"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("route-map-navigation")).toHaveTextContent(
      "navigation:route-2:3",
    );
    expect(screen.getByTestId("route-map-navigation")).not.toHaveTextContent(
      "route-1",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns to all preserved options without fetching", async () => {
    const response = makeRouteOptionsResponse(2);
    const fetchMock = vi.mocked(fetch);
    renderJourney("/navigation", response, 1);

    await userEvent.click(
      await screen.findByRole("button", { name: "Back to route options" }),
    );

    expect(await screen.findAllByRole("article")).toHaveLength(2);
    expect(screen.getByTestId("route-map-options")).toHaveTextContent(
      "route-1,route-2",
    );
    expect(screen.getAllByRole("tab")[1]).toHaveAttribute(
      "aria-selected",
      "true",
    );
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
    renderJourney("/routes/options", makeRouteOptionsResponse(3));

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

  it("changes active route details from each selector without fetching", async () => {
    const fetchMock = vi.mocked(fetch);
    renderJourney("/routes/options", makeRouteOptionsResponse(3));

    const selectors = await screen.findAllByRole("tab");
    const activeDetail = screen.getByRole("tabpanel");
    expect(selectors[0]).toHaveAttribute("aria-selected", "true");
    expect(within(activeDetail).getByText("≈ 8 movements/min")).toBeInTheDocument();

    await userEvent.click(selectors[1]);
    expect(selectors[1]).toHaveAttribute("aria-selected", "true");
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
    const { unmount } = renderJourney("/routes/options", zeroResponse);
    expect(
      (await screen.findAllByText("≈ 0 movements/min")).length,
    ).toBeGreaterThan(0);
    unmount();

    renderJourney("/routes/options", makeRouteOptionsResponse(1, "UNKNOWN"));
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

  it.each(["/routes/options", "/navigation", "/arrival"])(
    "redirects unsafe direct access to %s back to Search",
    async (path) => {
      renderJourney(path);

      expect(await screen.findByText("Safe search page")).toBeInTheDocument();
    },
  );
});
