const API_URL = import.meta.env.VITE_API_URL || "/mock-data";

/**
 * True when we are pointed at the static fixtures rather than a real backend.
 * The two speak the same shapes but not the same paths: `/mock-data` serves
 * `segments.json`, the API serves `/segments`.
 */
export const MOCK_MODE = API_URL.replace(/\/$/, "").endsWith("/mock-data");

/** `"segments"` -> `segments.json` on fixtures, `segments` against the API. */
export function resource(name: string): string {
  return MOCK_MODE ? `${name}.json` : name;
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const response = await fetch(
    `${API_URL.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`,
  );

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}