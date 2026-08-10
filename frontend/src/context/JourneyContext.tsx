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
  WalkingRoute,
  WalkingRouteSearchRequest,
} from "../types/route";

interface JourneyState {
  alertVisible: boolean;
  destination: JourneyLocation | null;
  origin: JourneyLocation | null;
  preference: CrowdPreference;
  routes: WalkingRoute[];
  selectedRoute: WalkingRoute | null;
  startedAt: string | null;
  statusMessage: string | null;
}

interface JourneyContextValue extends JourneyState {
  continueCurrentRoute: () => void;
  resetJourney: () => void;
  selectRoute: (route: WalkingRoute) => void;
  setDraftLocation: (
    field: "destination" | "origin",
    location: JourneyLocation | null,
  ) => void;
  setSearchResults: (
    request: WalkingRouteSearchRequest,
    routes: WalkingRoute[],
  ) => void;
  showAlertPreview: () => void;
  startPreviewAlternative: () => void;
}

const INITIAL_STATE: JourneyState = {
  alertVisible: false,
  destination: null,
  origin: null,
  preference: "PREFER_QUIETER",
  routes: [],
  selectedRoute: null,
  startedAt: null,
  statusMessage: null,
};

const JourneyContext = createContext<JourneyContextValue | null>(null);

const CROWD_ORDER = { LOW: 0, MEDIUM: 1, HIGH: 2 } as const;

export function JourneyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<JourneyState>(INITIAL_STATE);

  const value = useMemo<JourneyContextValue>(
    () => ({
      ...state,
      continueCurrentRoute: () => {
        setState((current) => ({
          ...current,
          alertVisible: false,
          statusMessage: "Continuing the current preview route.",
        }));
      },
      resetJourney: () => setState(INITIAL_STATE),
      selectRoute: (route) => {
        setState((current) => ({
          ...current,
          alertVisible: false,
          selectedRoute: route,
          startedAt: new Date().toISOString(),
          statusMessage: null,
        }));
      },
      setDraftLocation: (field, location) => {
        setState((current) => ({
          ...current,
          [field]: location,
          alertVisible: false,
          routes: [],
          selectedRoute: null,
          startedAt: null,
          statusMessage: null,
        }));
      },
      setSearchResults: (request, routes) => {
        setState({
          alertVisible: false,
          destination: request.destination,
          origin: request.origin,
          preference: request.preference,
          routes,
          selectedRoute: null,
          startedAt: null,
          statusMessage: null,
        });
      },
      showAlertPreview: () => {
        setState((current) => ({
          ...current,
          alertVisible: true,
          statusMessage: null,
        }));
      },
      startPreviewAlternative: () => {
        setState((current) => {
          if (!current.selectedRoute) {
            return current;
          }

          const selectedRoute = current.selectedRoute;
          const alternative = [...current.routes]
            .filter(
              (route) =>
                route.id !== selectedRoute.id &&
                CROWD_ORDER[route.crowdLevel] <
                  CROWD_ORDER[selectedRoute.crowdLevel],
            )
            .sort(
              (left, right) =>
                CROWD_ORDER[left.crowdLevel] - CROWD_ORDER[right.crowdLevel],
            )[0];

          if (!alternative) {
            return {
              ...current,
              alertVisible: false,
              statusMessage:
                "No lower-crowd alternative is available in the Phase 1 preview.",
            };
          }

          return {
            ...current,
            alertVisible: false,
            selectedRoute: alternative,
            statusMessage: `Preview route updated to ${alternative.name}.`,
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
