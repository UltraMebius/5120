import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { JourneyProvider } from "./context/JourneyContext";
import "mapbox-gl/dist/mapbox-gl.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <JourneyProvider>
        <App />
      </JourneyProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
