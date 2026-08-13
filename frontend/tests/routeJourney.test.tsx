import { useEffect, useState, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { JourneyProvider, useJourney } from "../src/context/JourneyContext";
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
      <Route path="/arrival" element={<div>Arrival</div>} />
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
      expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(
        routeCount,
      );
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
    renderJourney("/routes/options", makeRouteOptionsResponse(1, "LIVE"));

    expect(await screen.findByText("CALMEST")).toBeInTheDocument();
    expect(screen.getByText("FASTEST")).toBeInTheDocument();
    expect(screen.getByText("≈ 18 movements/min")).toBeInTheDocument();
    expect(screen.getAllByText("Live sensor estimate").length).toBeGreaterThan(
      0,
    );
  });

  it("distinguishes historical evidence from unavailable/null activity", async () => {
    const { unmount } = renderJourney(
      "/routes/options",
      makeRouteOptionsResponse(1, "HISTORICAL_ESTIMATE"),
    );
    expect(
      await screen.findAllByText("Historical estimate"),
    ).not.toHaveLength(0);
    expect(screen.queryByText("Live sensor estimate")).not.toBeInTheDocument();
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

    const buttons = await screen.findAllByRole("button", {
      name: /select route/i,
    });
    await userEvent.click(buttons[1]);

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
      await screen.findByRole("button", { name: "Exit" }),
    );

    expect(
      await screen.findByText("Home selected none, options 0"),
    ).toBeInTheDocument();
  });

  it.each(["/routes/options", "/navigation"])(
    "redirects unsafe direct access to %s back to Search",
    async (path) => {
      renderJourney(path);

      expect(await screen.findByText("Safe search page")).toBeInTheDocument();
    },
  );
});
