import { apiGet } from "./client";
import type { Segment } from "../types/api";

export function getSegments(): Promise<Segment[]> {
  return apiGet<Segment[]>("segments.json");
}