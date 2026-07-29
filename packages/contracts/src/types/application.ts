/**
 * ApplicationStatus represents the full set of states in the state machine.
 *
 * Safety invariant (initial release):
 *   When INITIAL_SUBMISSION_MODE=stop_before_submit, transitions to "submitted"
 *   are unconditionally blocked. The "approved" state always flows to
 *   "stopped_before_submit", never to "submitted".
 *
 *   The "submitted" value exists in the type for future releases only and
 *   must never be reachable in initial mode.
 */
export type ApplicationStatus =
  | "draft"
  | "matched"
  | "packet_draft"
  | "packet_ready"
  | "human_review"
  | "approved"
  | "stopped_before_submit"
  | "submitted"; // UNREACHABLE in initial release — future explicit gate only

export type EventTrigger = "system" | "human";

export interface ApplicationEvent {
  id: string;
  applicationId: string;
  fromStatus: ApplicationStatus | null;
  toStatus: ApplicationStatus;
  triggeredBy: EventTrigger;
  actorId: string | null;
  note: string | null;
  createdAt: string; // ISO 8601
}

/**
 * Keys stay wire-shaped (snake_case) on purpose: a fingerprint is an opaque
 * blob that must be echoed back to the API byte-identical when an assisted run
 * starts, so the dashboard client never rewrites its keys.
 */
export interface PacketFingerprint {
  profile_version: number;
  resume_version: number | null;
  cover_letter_version: number | null;
  answer_versions: Record<string, number>;
  job_snapshot_hash: string;
  packet_hash: string;
}

export interface Application {
  id: string;
  jobId: string;
  candidateProfileId: string;
  status: ApplicationStatus;
  packetFingerprint: PacketFingerprint | null;
  events: ApplicationEvent[];
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

export interface ApplicationSummary {
  id: string;
  jobId: string;
  candidateProfileId: string;
  status: ApplicationStatus;
  createdAt: string;
  updatedAt: string;
}

/** Payload for `POST /api/v1/applications` — starts an application for a job. */
export interface ApplicationCreateRequest {
  jobId: string;
  candidateProfileId: string;
  profileVersion: number | null;
  note: string | null;
}

export interface TransitionRequest {
  targetStatus: ApplicationStatus;
  note: string | null;
}
