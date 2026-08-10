function readPath(value: string | undefined, fallback: string): string {
  const normalizedValue = value?.trim();
  return normalizedValue || fallback;
}

export const APP_CONFIG = Object.freeze({
  apiBaseUrl: readPath(
    import.meta.env.VITE_API_BASE_URL,
    "http://localhost:8000",
  ).replace(/\/$/, ""),
  homeRoute: readPath(import.meta.env.VITE_HOME_ROUTE, "/home"),
});
