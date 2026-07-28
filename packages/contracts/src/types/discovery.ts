export type DiscoveryRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export type DiscoveryEventType =
  | "run_started"
  | "batch_discovered"
  | "run_completed"
  | "run_failed"
  | "adapter_error";

export interface DiscoveryRun {
  id: string;
  source: string;
  companyId: string;
  status: DiscoveryRunStatus;
  idempotencyKey: string;
  jobsDiscovered: number;
  jobsUpserted: number;
  jobsSkipped: number;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface DiscoveryRunSummary {
  id: string;
  source: string;
  companyId: string;
  status: DiscoveryRunStatus;
  jobsDiscovered: number;
  jobsUpserted: number;
  jobsSkipped: number;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface DiscoveryRunEvent {
  id: string;
  discoveryRunId: string;
  eventType: DiscoveryEventType;
  detail: Record<string, unknown>;
  createdAt: string;
}
