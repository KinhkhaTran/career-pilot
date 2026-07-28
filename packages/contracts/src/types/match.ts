export interface MatchExplanation {
  skills: { matched: string[]; required: string[]; ratio: number };
  title: { overlap: string[]; job_tokens: string[]; ratio: number };
  experience: { overlap: string[]; ratio: number };
  education: { matched: string[]; ratio: number };
  weights: { skills: number; title: number; experience: number; education: number };
}

export interface JobMatch {
  id: string;
  jobId: string;
  candidateProfileId: string;
  profileVersion: number;
  inputFingerprint: string;
  eligible: boolean;
  score: number;
  reasons: string[];
  explanation: MatchExplanation;
  createdAt: string | null;
}
