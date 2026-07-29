/**
 * Assisted-run contracts.
 *
 * An assisted run drives the in-process mock ATS sandbox only: `targetUrl` is
 * always a `mock-ats://` address and the plan has no submit action, so every run
 * terminates at `stopped_before_submit`.
 */
export type BrowserRunStatus =
  | "queued"
  | "running"
  | "paused"
  | "stopped_before_submit"
  | "failed";

/** One planned or executed action. `detail` is passed through verbatim. */
export interface BrowserRunPlanStep {
  action: string;
  detail: Record<string, unknown>;
}

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
  mode: string;
  targetKind: string;
  /** Always a `mock-ats://` sandbox address. */
  targetUrl: string;
  plan: BrowserRunPlanStep[];
  /** Index of the next planned step to execute. */
  cursor: number;
  createdAt: string | null;
  pausedAt: string | null;
  completedAt: string | null;
  steps: BrowserRunStep[];
  events: BrowserRunEvent[];
  screenshots: BrowserScreenshot[];
}

export interface BrowserRunLaunchContext {
  /**
   * Opaque payloads echoed back to the API unchanged — the start request only
   * succeeds when they deep-equal the approved application's inputs, so these
   * are never key-rewritten by the dashboard client.
   */
  packetFingerprint: Record<string, unknown>;
  immutableInputs: Record<string, unknown>;
  approvedFields: Record<string, string>;
  /** Sandbox target the assisted run will drive (`mock-ats://…`). */
  applicationUrl: string;
  /** The real posting, shown for manual reading only. Never automated. */
  employerUrl: string;
  mockAtsLabel: string;
  plannedSteps: BrowserRunPlanStep[];
}

export interface BrowserRunStartRequest {
  packetFingerprint: Record<string, unknown>;
  immutableInputs: Record<string, unknown>;
  approvedFields: Record<string, string>;
  applicationUrl: string;
  headless?: false;
  adapter?: string;
}
