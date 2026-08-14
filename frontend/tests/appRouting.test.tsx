import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import App from "../src/App";

vi.mock("../src/pages/ArrivalPage", () => ({
  default: () => <div>Arrival page</div>,
}));

vi.mock("../src/pages/HomePage", () => ({
  default: () => <div>Home page</div>,
}));

vi.mock("../src/pages/NavigationPage", () => ({
  default: () => <div>Navigation page</div>,
}));

vi.mock("../src/pages/RouteSearchPage", () => ({
  default: () => <div>Route search page</div>,
}));

describe("application routing", () => {
  it("routes /navigation to the merged Navigation page", () => {
    render(
      <MemoryRouter initialEntries={["/navigation"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByText("Navigation page")).toBeInTheDocument();
  });

  it("no longer exposes the obsolete /routes/options page", async () => {
    render(
      <MemoryRouter initialEntries={["/routes/options"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Route search page")).toBeInTheDocument();
  });
});
