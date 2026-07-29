import type { JobSummary } from "./job.js";
import type { JobMatch } from "./match.js";
import type { CandidatePreferences } from "./preference.js";

/** Request body for `POST /api/v1/jobs/search`. */
export interface JobSearchInput {
  profileId: string;
  profileVersion: number | null;
  eligibleOnly: boolean;
  limit: number;
}

/** One ranked job plus the persisted match that explains its score. */
export interface JobSearchResult {
  job: JobSummary;
  sourceUrl: string;
  match: JobMatch;
}

/**
 * Search reads only jobs already stored by discovery — it performs no outbound
 * requests and never creates or mutates an application.
 */
export interface JobSearchResponse {
  profileId: string;
  profileVersion: number;
  preferences: CandidatePreferences;
  scanned: number;
  filteredOut: number;
  results: JobSearchResult[];
}
