/**
 * Candidate profile contracts.
 *
 * Field names mirror the API payloads (`app/schemas/profile.py`) after the
 * dashboard's snake_case -> camelCase rewrite, so a profile read from
 * `GET /api/v1/profiles/{id}` can be written straight back to
 * `PUT /api/v1/profiles/{id}` without losing data.
 */
export interface ContactInfo {
  email: string;
  phone: string | null;
  location: string | null;
  linkedin: string | null;
  github: string | null;
  website: string | null;
}

export interface WorkExperience {
  company: string;
  title: string;
  startDate: string; // YYYY-MM
  endDate: string | null; // YYYY-MM, null = current
  isCurrent: boolean;
  location: string | null;
  isRemote: boolean;
  description: string | null;
  achievements: string[];
  technologies: string[];
}

export interface Education {
  institution: string;
  degree: string;
  fieldOfStudy: string | null;
  startDate: string | null; // YYYY-MM
  endDate: string | null; // YYYY-MM
  gpa: number | null;
  honors: string[];
  activities: string[];
}

export interface Certification {
  name: string;
  issuer: string;
  issuedDate: string | null; // YYYY-MM
  expiryDate: string | null; // YYYY-MM
  credentialId: string | null;
  credentialUrl: string | null;
}

export interface CandidateProfile {
  id: string;
  version: number;
  fullName: string;
  contactInfo: ContactInfo | null;
  summary: string | null;
  workExperience: WorkExperience[];
  education: Education[];
  certifications: Certification[];
  skills: string[];
  languages: string[];
  createdAt: string | null; // ISO 8601
  updatedAt: string | null; // ISO 8601
}

export interface CandidateProfileSummary {
  id: string;
  version: number;
  fullName: string;
  email: string | null;
  location: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

/**
 * Payload for `PUT /api/v1/profiles/{id}`.
 *
 * Profiles are append-only: writing this payload appends a new version rather
 * than mutating the current one, so every field must be sent, not just the
 * edited ones.
 */
export interface CandidateProfileInput {
  fullName: string;
  contactInfo: ContactInfo | null;
  summary: string | null;
  workExperience: WorkExperience[];
  education: Education[];
  certifications: Certification[];
  skills: string[];
  languages: string[];
}
