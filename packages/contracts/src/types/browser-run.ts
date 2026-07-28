export type BrowserRunStatus =
  | "queued"
  | "running"
  | "stopped_before_submit"
  | "paused"
  | "stopped_at_review"
  | "submitted"
  | "failed";

/** Why a supervised run handed control back to the human. */
export type PauseReason =
  | "not_at_application_form"
  | "unsupported_ats"
  | "missing_answer"
  | "low_confidence"
  | "legally_sensitive"
  | "attestation"
  | "captcha"
  | "mfa"
  | "identity_verification"
  | "login_required"
  | "validation_error"
  | "stopped_at_review";

export interface BrowserRunStep {
  id: string;
  sequence: number;
  action: string;
  detail: Record<string, unknown>;
  createdAt: string | null;
}

export interface BrowserRunEvent {
  id: string;
  sequence: number;
  eventType: string;
  detail: Record<string, unknown>;
  createdAt: string | null;
}

export interface BrowserScreenshot {
  id: string;
  sequence: number;
  label: string;
  path: string;
  sha256: string | null;
  createdAt: string | null;
}

export interface BrowserRun {
  id: string;
  applicationId: string;
  status: BrowserRunStatus;
  packetFingerprint: Record<string, unknown>;
  headless: boolean;
  adapterName: string;
  stoppedBeforeSubmit: boolean;
  /** SHA-256 of the reviewed Review-page summary; binds the approval token. */
  finalPageFingerprint: string | null;
  submitted: boolean;
  /** Proof-of-submission captured from the confirmation page, once submitted. */
  confirmation: Record<string, unknown> | null;
  submissionMode: "stop_before_submit" | "allow_submit";
  createdAt: string | null;
  completedAt: string | null;
  steps: BrowserRunStep[];
  events: BrowserRunEvent[];
  screenshots: BrowserScreenshot[];
}

/** Request body a human submits to authorise exactly one Submit click. */
export interface ApprovalTokenRequest {
  finalPageFingerprint: string;
  resumeVersion: number;
  confirm: true;
}

/**
 * A single-use token authorising one Submit click, bound to the exact
 * application/job/résumé/answer-set/run/final-page state (requirement 12).
 */
export interface ApprovalToken {
  id: string;
  token: string;
  tokenId: string;
  applicationId: string;
  browserRunId: string;
  resumeVersion: number;
  answerSetVersion: number;
  finalPageFingerprint: string;
  bindingDigest: string;
  consumed: boolean;
  createdAt: string | null;
}

export interface BrowserRunLaunchContext {
  packetFingerprint: Record<string, unknown>;
  immutableInputs: Record<string, unknown>;
  approvedFields: Record<string, string>;
  applicationUrl: string;
}

export interface BrowserRunStartRequest extends BrowserRunLaunchContext {
  packetFingerprint: Record<string, unknown>;
  immutableInputs: Record<string, unknown>;
  approvedFields: Record<string, string>;
  applicationUrl: string;
  headless?: false;
  adapter?: string;
}
