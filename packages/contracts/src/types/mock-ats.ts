/**
 * Receipt for a submission delivered to the in-process mock ATS sandbox.
 *
 * SAFETY: a receipt only ever describes the local `mock-ats://` sandbox board
 * that ships with CareerPilot. No employer receives a sandbox submission, and
 * recording one never advances an application past `stopped_before_submit`.
 */
export interface MockAtsReceipt {
  id: string;
  boardToken: string;
  externalJobId: string;
  applicationId: string;
  browserRunId: string | null;
  confirmationCode: string;
  packetHash: string | null;
  payload: Record<string, string>;
  receivedAt: string | null;
  /** Always true; rendered wherever a receipt is displayed. */
  isMock: boolean;
}
