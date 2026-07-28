import { describe, expect, it } from "vitest";
import type { ApplicationStatus } from "@career-pilot/contracts";

const initialStatuses: ApplicationStatus[] = [
  "draft",
  "matched",
  "packet_draft",
  "packet_ready",
  "human_review",
  "approved",
  "stopped_before_submit",
];

describe("initial submission boundary", () => {
  it("represents the terminal stop-before-submit state", () => {
    expect(initialStatuses.at(-1)).toBe("stopped_before_submit");
    expect(initialStatuses).not.toContain("submitted");
  });
});
