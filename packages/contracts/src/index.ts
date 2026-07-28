export type * from "./types/index.js";

// State machine constants mirrored from the API service for client use
export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  matched: "Matched",
  packet_draft: "Packet Draft",
  packet_ready: "Packet Ready",
  human_review: "Human Review",
  approved: "Approved",
  stopped_before_submit: "Stopped — Awaiting Authorization",
  submitted: "Submitted", // unreachable in initial release
};

export const TERMINAL_STATUSES = [
  "stopped_before_submit",
  "submitted",
] as const;

export const INITIAL_MODE_BLOCKED_STATUSES = ["submitted"] as const;
