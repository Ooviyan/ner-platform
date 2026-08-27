import { apiGet } from "./client";
import type { Route } from "../types/api";

export function getRoutes(): Promise<Route[]> {
  return apiGet<Route[]>("routes.json");
}