import { describe, expect, it } from "vitest";
import { camelizeKeys, snakeizeKeys } from "./api";

describe("wire key rewriting", () => {
  it("camelizes ordinary payload keys", () => {
    expect(
      camelizeKeys({ candidate_profile_id: "p1", input_fingerprint: "abc", nested: { job_id: "j1" } })
    ).toEqual({ candidateProfileId: "p1", inputFingerprint: "abc", nested: { jobId: "j1" } });
  });

  it("leaves opaque blobs byte-identical so an assisted run can echo them back", () => {
    const wire = {
      packet_fingerprint: { profile_version: 3, packet_hash: "h" },
      immutable_inputs: { job_snapshot: { snapshot_hash: "s" } },
      approved_fields: { full_name: "Ada", cover_letter: "Dear team" },
    };
    // The API compares these field-for-field before allowing a run to start.
    expect(camelizeKeys(wire)).toEqual({
      packetFingerprint: { profile_version: 3, packet_hash: "h" },
      immutableInputs: { job_snapshot: { snapshot_hash: "s" } },
      approvedFields: { full_name: "Ada", cover_letter: "Dear team" },
    });
  });

  it("keeps the contract-shaped match explanation intact", () => {
    const explained = camelizeKeys<{ explanation: { title: { job_tokens: string[] } } }>({
      explanation: { title: { overlap: ["engineer"], job_tokens: ["senior", "engineer"] } },
    });
    expect(explained.explanation.title.job_tokens).toEqual(["senior", "engineer"]);
  });

  it("snakeizes request bodies for the API", () => {
    expect(
      snakeizeKeys({
        fullName: "Ada",
        contactInfo: { email: "a@example.com", linkedin: null },
        workExperience: [{ isCurrent: true, startDate: "2022-01" }],
      })
    ).toEqual({
      full_name: "Ada",
      contact_info: { email: "a@example.com", linkedin: null },
      work_experience: [{ is_current: true, start_date: "2022-01" }],
    });
  });
});
