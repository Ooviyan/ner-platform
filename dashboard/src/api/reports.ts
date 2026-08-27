import { apiGet } from "./client";
import type { Report } from "../types/api";

export function getReports(): Promise<Report[]> {
  return apiGet<Report[]>("reports.json");
}