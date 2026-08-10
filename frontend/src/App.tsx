import { Navigate, Route, Routes } from "react-router-dom";

import { APP_CONFIG } from "./config";
import ArrivalPage from "./pages/ArrivalPage";
import HomeIntegrationPage from "./pages/HomeIntegrationPage";
import NavigationPage from "./pages/NavigationPage";
import RouteOptionsPage from "./pages/RouteOptionsPage";
import RouteSearchPage from "./pages/RouteSearchPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/routes/search" replace />} />
      <Route path="/routes/search" element={<RouteSearchPage />} />
      <Route path="/routes/options" element={<RouteOptionsPage />} />
      <Route path="/navigation" element={<NavigationPage />} />
      <Route path="/arrival" element={<ArrivalPage />} />
      <Route path={APP_CONFIG.homeRoute} element={<HomeIntegrationPage />} />
      <Route path="*" element={<Navigate to="/routes/search" replace />} />
    </Routes>
  );
}

export default App;
