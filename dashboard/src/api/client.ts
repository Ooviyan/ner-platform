const API_URL = import.meta.env.VITE_API_URL || "/mock-data";

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