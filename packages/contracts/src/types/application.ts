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

export interface PacketFingerprint {
  profileVersion: number;
  resumeVersion: number;
  answerVersions: Record<string, number>; // questionId → version
  jobSnapshotHash: string;
  packetHash: string;
  generatedAt: string; // ISO 8601
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
  status: ApplicationStatus;
  createdAt: string;
  updatedAt: string;
}

export interface TransitionRequest {
  targetStatus: ApplicationStatus;
  note: string | null;
}
