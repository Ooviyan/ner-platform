import { apiGet, resource } from "./client";
import type { Report } from "../types/api";

export function getReports(): Promise<Report[]> {
  return apiGet<Report[]>(resource("reports"));
}