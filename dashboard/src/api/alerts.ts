import { apiGet, resource } from "./client";
import type { Alert } from "../types/api";

export function getAlerts(): Promise<Alert[]> {
  return apiGet<Alert[]>(resource("alerts"));
}
