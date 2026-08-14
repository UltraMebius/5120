import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { JourneyProvider, useJourney } from "../src/context/JourneyContext";
import RouteSearchPage from "../src/pages/RouteSearchPage";
import { RouteOptionsApiError } from "../src/services/api";
import type { RouteOptionsSearchRequest } from "../src/types/routeOptions";
import {
  makeMultiRoleRouteOptionsResponse,
  SEARCH_REQUEST,
} from "./fixtures";

vi.mock("../src/components/layout/AppHeader", () => ({
  default: () => <div>Header</div>,
}));

vi.mock("../src/components/map/MapboxMap", () => ({
  default: () => <div>Search map</div>,
}));

vi.mock("../src/components/route/RouteSearchForm", () => ({
  default: ({
    isLoading,
    onSearch,
  }: {
    isLoading: boolean;
    onSearch: (request: RouteOptionsSearchRequest) => Promise<void>;
  }) => (
    <button
      disabled={isLoading}
      onClick={() => void onSearch(SEARCH_REQUEST)}
      type="button"
    >
      {isLoading ? "Finding walking routes..." : "Submit mocked search"}
    </button>
  ),
}));

function NavigationProbe() {
  const journey = useJourney();
  return (
    <div>
      Stored {journey.routeOptions.length} routes for {journey.origin?.label}
      <span>
        IDs {journey.routeOptions.map((route) => route.routeId).join(",")}
      </span>
    </div>
  );
}

function renderSearchPage() {
  return render(
    <MemoryRouter initialEntries={["/routes/search"]}>
      <JourneyProvider>
        <Routes>
          <Route path="/routes/search" element={<RouteSearchPage />} />
          <Route path="/navigation" element={<NavigationProbe />} />
        </Routes>
      </JourneyProvider>
    </MemoryRouter>,
  );
}

describe("RouteSearchPage", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("accepts a multi-role response and navigates directly to Navigation", async () => {
    const response = makeMultiRoleRouteOptionsResponse();
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(response), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderSearchPage();

    await userEvent.click(
      screen.getByRole("button", { name: "Submit mocked search" }),
    );

    expect(
      await screen.findByText("Stored 3 routes for Melbourne Central"),
    ).toBeInTheDocument();
    expect(screen.getByText("IDs route-1,route-2,route-3")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(console.error).not.toHaveBeenCalled();
  });

  it.each([502, 503])(
    "shows a safe message for HTTP %i and remains on Search",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>().mockResolvedValue(
          new Response("{}", {
            headers: { "Content-Type": "application/json" },
            status,
          }),
        ),
      );
      renderSearchPage();

      await userEvent.click(
        screen.getByRole("button", { name: "Submit mocked search" }),
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "We couldn't find walking routes for those locations. Please try again.",
      );
      expect(
        screen.getByRole("button", { name: "Submit mocked search" }),
      ).toBeInTheDocument();
      expect(console.error).toHaveBeenCalledWith(
        "Unable to load route options.",
        expect.any(RouteOptionsApiError),
      );
    },
  );

  it("shows a concise loading state and disables repeat submission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockReturnValue(
        new Promise<Response>(() => undefined),
      ),
    );
    renderSearchPage();

    await userEvent.click(
      screen.getByRole("button", { name: "Submit mocked search" }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Finding walking routes...",
    );
    expect(
      screen.getByRole("button", { name: "Finding walking routes..." }),
    ).toBeDisabled();
  });
});
