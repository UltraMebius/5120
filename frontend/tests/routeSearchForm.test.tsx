import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RouteSearchForm from "../src/components/route/RouteSearchForm";
import { SEARCH_REQUEST } from "./fixtures";

function renderForm(
  overrides: Partial<React.ComponentProps<typeof RouteSearchForm>> = {},
) {
  const onSearch = vi.fn().mockResolvedValue(undefined);
  render(
    <RouteSearchForm
      initialDestination={null}
      initialOrigin={null}
      isLoading={false}
      onDraftLocationChange={vi.fn()}
      onSearch={onSearch}
      {...overrides}
    />,
  );
  return onSearch;
}

describe("RouteSearchForm", () => {
  it("requires origin and destination without rendering a tolerance selector", () => {
    const onSearch = renderForm();

    fireEvent.click(
      screen.getByRole("button", { name: /find walking routes/i }),
    );

    expect(screen.getByText("Origin is required.")).toBeInTheDocument();
    expect(screen.getByText("Destination is required.")).toBeInTheDocument();
    expect(screen.queryByText(/crowd tolerance/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByText(/^LOW$|^MEDIUM$|^HIGH$/)).not.toBeInTheDocument();
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("submits selected locations with no preference", () => {
    const onSearch = renderForm({
      initialDestination: SEARCH_REQUEST.destination,
      initialOrigin: SEARCH_REQUEST.origin,
    });

    fireEvent.click(
      screen.getByRole("button", { name: /find walking routes/i }),
    );

    expect(onSearch).toHaveBeenCalledTimes(1);
    expect(onSearch).toHaveBeenCalledWith(SEARCH_REQUEST);
    expect(onSearch.mock.calls[0][0]).not.toHaveProperty("preference");
  });

  it("blocks a second synchronous submission while the first is pending", () => {
    let resolveSearch: (() => void) | undefined;
    const pendingSearch = new Promise<void>((resolve) => {
      resolveSearch = resolve;
    });
    const onSearch = vi.fn().mockReturnValue(pendingSearch);
    renderForm({
      initialDestination: SEARCH_REQUEST.destination,
      initialOrigin: SEARCH_REQUEST.origin,
      onSearch,
    });
    const form = screen
      .getByRole("button", { name: /find walking routes/i })
      .closest("form");
    expect(form).not.toBeNull();

    fireEvent.submit(form!);
    fireEvent.submit(form!);

    expect(onSearch).toHaveBeenCalledTimes(1);
    resolveSearch?.();
  });
});
