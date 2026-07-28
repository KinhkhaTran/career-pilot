export type BrowserRunStatus = "queued" | "running" | "stopped_before_submit" | "failed";

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
  createdAt: string | null;
  completedAt: string | null;
  steps: BrowserRunStep[];
  events: BrowserRunEvent[];
  screenshots: BrowserScreenshot[];
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
