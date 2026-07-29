export type JobSource =
  | "greenhouse"
  | "lever"
  | "ashby"
  | "workday"
  | "icims"
  | "direct"
  | "other";

export type JobStatus =
  | "discovered"
  | "normalized"
  | "matched"
  | "ignored"
  | "expired";

export type EmploymentType =
  | "full_time"
  | "part_time"
  | "contract"
  | "internship"
  | "temporary";

export interface SalaryRange {
  min: number | null;
  max: number | null;
  currency: string;
  period: "annual" | "monthly" | "hourly";
}

export interface Job {
  id: string;
  externalId: string | null;
  source: JobSource;
  sourceUrl: string;
  title: string;
  company: string;
  location: string | null;
  isRemote: boolean;
  employmentType: EmploymentType | null;
  salaryRange: SalaryRange | null;
  description: string;
  requirements: string[];
  niceToHave: string[];
  technologies: string[];
  status: JobStatus;
  snapshotHash: string;
  discoveredAt: string; // ISO 8601
  postedAt: string | null; // ISO 8601
  expiresAt: string | null; // ISO 8601
  normalizedAt: string | null;
}

export interface JobSummary {
  id: string;
  title: string;
  company: string;
  location: string | null;
  isRemote: boolean;
  employmentType: EmploymentType | null;
  status: JobStatus;
  source: JobSource;
  discoveredAt: string;
  postedAt: string | null;
}
