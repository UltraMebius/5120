import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { CrowdPreference } from "../types/crowd";
import type {
  JourneyLocation,
  RouteRankingStatus,
  WalkingRoute,
  WalkingRouteSearchRequest,
  WalkingRoutesResult,
} from "../types/route";

interface JourneyState {
  acknowledgedAlertRouteIds: string[];
  destination: JourneyLocation | null;
  origin: JourneyLocation | null;
  preference: CrowdPreference;
  rankingStatus: RouteRankingStatus;
  recommendedRouteId: string | null;
  routes: WalkingRoute[];
  selectedRoute: WalkingRoute | null;
  startedAt: string | null;
  statusMessage: string | null;
}

interface JourneyContextValue extends JourneyState {
  acknowledgeCrowdAlert: (routeId: string) => void;
  resetJourney: () => void;
  selectRoute: (route: WalkingRoute) => void;
  setDraftLocation: (
    field: "destination" | "origin",
    location: JourneyLocation | null,
  ) => void;
  setSearchResults: (
    request: WalkingRouteSearchRequest,
    result: WalkingRoutesResult,
  ) => void;
  switchToAlternativeRoute: (route: WalkingRoute) => void;
}

const INITIAL_STATE: JourneyState = {
  acknowledgedAlertRouteIds: [],
  destination: null,
  origin: null,
  preference: "PREFER_QUIETER",
  rankingStatus: "NOT_EVALUATED",
  recommendedRouteId: null,
  routes: [],
  selectedRoute: null,
  startedAt: null,
  statusMessage: null,
};

const JourneyContext = createContext<JourneyContextValue | null>(null);

export function JourneyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<JourneyState>(INITIAL_STATE);

  const value = useMemo<JourneyContextValue>(
    () => ({
      ...state,
      acknowledgeCrowdAlert: (routeId) => {
        setState((current) => {
          if (current.selectedRoute?.id !== routeId) {
            return current;
          }
          return {
            ...current,
            acknowledgedAlertRouteIds: current.acknowledgedAlertRouteIds.includes(
              routeId,
            )
              ? current.acknowledgedAlertRouteIds
              : [...current.acknowledgedAlertRouteIds, routeId],
            statusMessage:
              "Crowd alert acknowledged. Continuing the current route.",
          };
        });
      },
      resetJourney: () => setState(INITIAL_STATE),
      selectRoute: (route) => {
        setState((current) => ({
          ...current,
          acknowledgedAlertRouteIds: [],
          selectedRoute: route,
          startedAt: new Date().toISOString(),
          statusMessage: null,
        }));
      },
      setDraftLocation: (field, location) => {
        setState((current) => ({
          ...current,
          [field]: location,
          acknowledgedAlertRouteIds: [],
          rankingStatus: "NOT_EVALUATED",
          recommendedRouteId: null,
          routes: [],
          selectedRoute: null,
          startedAt: null,
          statusMessage: null,
        }));
      },
      setSearchResults: (request, result) => {
        setState({
          acknowledgedAlertRouteIds: [],
          destination: request.destination,
          origin: request.origin,
          preference: result.preference,
          rankingStatus: result.rankingStatus,
          recommendedRouteId: result.recommendedRouteId,
          routes: result.routes,
          selectedRoute: null,
          startedAt: null,
          statusMessage: null,
        });
      },
      switchToAlternativeRoute: (route) => {
        setState((current) => {
          const existingRoute = current.routes.find(
            (candidate) => candidate.id === route.id,
          );
          if (!existingRoute || existingRoute.id === current.selectedRoute?.id) {
            return current;
          }
          return {
            ...current,
            selectedRoute: existingRoute,
            statusMessage: "Route changed to a lower-stimulation alternative.",
          };
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
