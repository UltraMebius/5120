function readPath(name: string, fallback: string): string {
  const value = (import.meta.env[name] as string | undefined)?.trim();
  return value || fallback;
}

export const APP_CONFIG = Object.freeze({
  apiBaseUrl: readPath("VITE_API_BASE_URL", "http://localhost:8000").replace(
    /\/$/,
    "",
  ),
  homeRoute: readPath("VITE_HOME_ROUTE", "/home"),
});
