import { apiGet, resource } from "./client";
import type { Route } from "../types/api";

export function getRoutes(): Promise<Route[]> {
  return apiGet<Route[]>(resource("routes"));
}