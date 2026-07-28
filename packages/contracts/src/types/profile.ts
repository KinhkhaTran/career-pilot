export interface ContactInfo {
  email: string;
  phone: string | null;
  linkedinUrl: string | null;
  githubUrl: string | null;
  portfolioUrl: string | null;
  location: string | null;
}

export interface WorkExperience {
  id: string;
  company: string;
  title: string;
  startDate: string; // YYYY-MM
  endDate: string | null; // YYYY-MM, null = present
  isCurrent: boolean;
  description: string;
  achievements: string[];
  technologies: string[];
}

export interface Education {
  id: string;
  institution: string;
  degree: string;
  field: string;
  startDate: string; // YYYY-MM
  endDate: string | null; // YYYY-MM
  gpa: number | null;
  honors: string[];
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  issuedDate: string; // YYYY-MM
  expiryDate: string | null; // YYYY-MM
  credentialId: string | null;
}

export interface CandidateProfile {
  id: string;
  version: number;
  fullName: string;
  contact: ContactInfo;
  summary: string;
  workExperience: WorkExperience[];
  education: Education[];
  certifications: Certification[];
  skills: string[];
  languages: string[];
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

export interface CandidateProfileSummary {
  id: string;
  version: number;
  fullName: string;
  updatedAt: string;
}
