import { apiGet, resource } from "./client";
import type { Segment } from "../types/api";

export function getSegments(): Promise<Segment[]> {
  return apiGet<Segment[]>(resource("segments"));
}