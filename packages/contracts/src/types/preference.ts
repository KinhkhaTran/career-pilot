/**
 * Versioned candidate search preferences.
 *
 * `remoteOnly`, `allowedLocations`, and `employmentTypes` are hard eligibility
 * constraints applied by the matching engine; `keywords` and `minSalary` filter
 * stored jobs before scoring.
 */
export interface CandidatePreferencesInput {
  remoteOnly: boolean;
  allowedLocations: string[];
  employmentTypes: string[];
  keywords: string[];
  minSalary: number | null;
}

export interface CandidatePreferences extends CandidatePreferencesInput {
  candidateProfileId: string;
  version: number;
  createdAt: string | null;
}
