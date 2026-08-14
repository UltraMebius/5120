import { Navigate, Route, Routes } from "react-router-dom";

import { APP_CONFIG } from "./config";
import ArrivalPage from "./pages/ArrivalPage";
import HomePage from "./pages/HomePage";
import NavigationPage from "./pages/NavigationPage";
import RouteSearchPage from "./pages/RouteSearchPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={APP_CONFIG.homeRoute} replace />} />
      <Route path="/routes/search" element={<RouteSearchPage />} />
      <Route path="/navigation" element={<NavigationPage />} />
      <Route path="/arrival" element={<ArrivalPage />} />
      <Route path={APP_CONFIG.homeRoute} element={<HomePage />} />
      <Route path="*" element={<Navigate to="/routes/search" replace />} />
    </Routes>
  );
}

export default App;
