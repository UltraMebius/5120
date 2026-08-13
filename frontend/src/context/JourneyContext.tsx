import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { JourneyLocation } from "../types/route";
import type {
  RouteOption,
  RouteOptionsResponse,
  RouteOptionsSearchRequest,
} from "../types/routeOptions";

interface JourneyState {
  destination: JourneyLocation | null;
  origin: JourneyLocation | null;
  routeOptions: RouteOption[];
  routeOptionsResponse: RouteOptionsResponse | null;
  selectedRoute: RouteOption | null;
  startedAt: string | null;
}

interface JourneyContextValue extends JourneyState {
  resetJourney: () => void;
  selectRoute: (route: RouteOption) => void;
  setDraftLocation: (
    field: "destination" | "origin",
    location: JourneyLocation | null,
  ) => void;
  setRouteOptions: (
    request: RouteOptionsSearchRequest,
    response: RouteOptionsResponse,
  ) => void;
}

const INITIAL_STATE: JourneyState = {
  destination: null,
  origin: null,
  routeOptions: [],
  routeOptionsResponse: null,
  selectedRoute: null,
  startedAt: null,
};

const JourneyContext = createContext<JourneyContextValue | null>(null);

export function JourneyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<JourneyState>(INITIAL_STATE);

  const value = useMemo<JourneyContextValue>(
    () => ({
      ...state,
      resetJourney: () => setState(INITIAL_STATE),
      selectRoute: (route) => {
        setState((current) => {
          const existingRoute = current.routeOptions.find(
            (candidate) => candidate.routeId === route.routeId,
          );
          if (!existingRoute) {
            return current;
          }

          return {
            ...current,
            selectedRoute: existingRoute,
            startedAt: new Date().toISOString(),
          };
        });
      },
      setDraftLocation: (field, location) => {
        setState((current) => ({
          ...current,
          [field]: location,
          routeOptions: [],
          routeOptionsResponse: null,
          selectedRoute: null,
          startedAt: null,
        }));
      },
      setRouteOptions: (request, response) => {
        setState({
          destination: request.destination,
          origin: request.origin,
          routeOptions: response.routes,
          routeOptionsResponse: response,
          selectedRoute: null,
          startedAt: null,
        });
      },
    }),
    [state],
  );

  return (
    <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>
  );
}

export function useJourney(): JourneyContextValue {
  const context = useContext(JourneyContext);

  if (!context) {
    throw new Error("useJourney must be used inside JourneyProvider.");
  }

  return context;
}
