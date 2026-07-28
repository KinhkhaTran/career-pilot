import type { PacketFingerprint } from "./application.js";

export type MaterialKind = "resume" | "cover_letter";

export interface ApplicationMaterial {
  id: string;
  applicationId: string;
  kind: MaterialKind;
  version: number;
  content: string;
  diff: string | null;
  sourceClaims: string[];
  reviewed: boolean;
}

export interface AnswerLibraryEntry {
  id: string;
  candidateProfileId: string;
  questionKey: string;
  question: string;
  answer: string;
  version: number;
  reviewed: boolean;
}

export interface GeneratedPacket {
  resume: ApplicationMaterial;
  coverLetter: ApplicationMaterial;
  fingerprint: PacketFingerprint;
}
