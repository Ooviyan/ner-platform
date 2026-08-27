// Internal UI/map types. These are NOT part of the mock-data API contract in
// src/types/api.ts — they describe derived categories and view state only.

export type RiskLevel = "normal" | "warning" | "critical";

export type SegmentStatus = "open" | "restricted" | "closed";

export type StatusFilterValue = "all" | SegmentStatus;

export type RiskFilterValue = "all" | RiskLevel;

export type ResourceStatus = "loading" | "success" | "empty" | "error";

export type SelectionKind = "segment" | "route" | "report";

// Bumping `token` (even when kind/id repeat) is what tells the map to re-run
// the camera move — selection alone only drives highlight state.
export interface FocusRequest {
  kind: SelectionKind;
  id: string;
  token: number;
}
