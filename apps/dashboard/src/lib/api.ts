import type {
  Application,
  ApplicationStatus,
  BrowserRun,
  BrowserRunLaunchContext,
  BrowserRunStartRequest,
  CandidatePreferences,
  CandidatePreferencesInput,
  CandidateProfile,
  CandidateProfileInput,
  CandidateProfileSummary,
  GeneratedPacket,
  JobSearchInput,
  JobSearchResponse,
  MockAtsReceipt,
} from "@career-pilot/contracts";

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

/** Carries the HTTP status so callers can treat 404/409 as flow states, not crashes. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Pull FastAPI's `detail` out of an error body so the UI can show the real reason. */
async function readError(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
  } catch {
    // Fall through to the status line.
  }
  return `API error ${res.status}: ${res.statusText}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  return res.json() as Promise<T>;
}

/**
 * The API serializes JSON in snake_case (Pydantic default); the shared
 * `@career-pilot/contracts` types are camelCase. Recursively rewrite object
 * keys so wire payloads conform to the contracts. Values are left untouched.
 *
 * Some payloads are opaque and must survive the round trip byte-identical:
 * a packet fingerprint and the immutable inputs are compared field-for-field by
 * the API before an assisted run may start, approved fields and sandbox payloads
 * are keyed by form field name, and a match explanation is a contract-shaped blob.
 * Values under those keys are passed through verbatim.
 */
const OPAQUE_KEYS: ReadonlySet<string> = new Set([
  "packet_fingerprint",
  "immutable_inputs",
  "approved_fields",
  "explanation",
  "fingerprint",
  "payload",
  "detail",
]);

export function camelizeKeys<T = unknown>(input: unknown, opaque = OPAQUE_KEYS): T {
  if (Array.isArray(input)) {
    return input.map((item) => camelizeKeys(item, opaque)) as T;
  }
  if (input !== null && typeof input === "object") {
    return Object.fromEntries(
      Object.entries(input as Record<string, unknown>).map(([key, value]) => [
        key.replace(/_([a-z0-9])/g, (_, char: string) => char.toUpperCase()),
        opaque.has(key) ? value : camelizeKeys(value, opaque),
      ])
    ) as T;
  }
  return input as T;
}

/** Inverse of `camelizeKeys` for request bodies the API reads as snake_case. */
export function snakeizeKeys<T = unknown>(input: unknown): T {
  if (Array.isArray(input)) {
    return input.map((item) => snakeizeKeys(item)) as T;
  }
  if (input !== null && typeof input === "object") {
    return Object.fromEntries(
      Object.entries(input as Record<string, unknown>).map(([key, value]) => [
        key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`),
        snakeizeKeys(value),
      ])
    ) as T;
  }
  return input as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const payload = await apiFetch<unknown>(path, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return camelizeKeys<T>(payload);
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const payload = await apiFetch<unknown>(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return camelizeKeys<T>(payload);
}

async function get<T>(path: string): Promise<T> {
  return camelizeKeys<T>(await apiFetch<unknown>(path));
}

// --- Profiles and preferences ------------------------------------------------

export async function listProfiles(): Promise<CandidateProfileSummary[]> {
  return get<CandidateProfileSummary[]>("/api/v1/profiles");
}

export async function getProfile(profileId: string): Promise<CandidateProfile> {
  return get<CandidateProfile>(`/api/v1/profiles/${profileId}`);
}

/** Profiles are append-only: this writes a new version and returns it. */
export async function saveProfile(
  profileId: string,
  input: CandidateProfileInput
): Promise<CandidateProfile> {
  return put<CandidateProfile>(`/api/v1/profiles/${profileId}`, snakeizeKeys(input));
}

/** Returns `null` when the candidate has never saved preferences. */
export async function getPreferences(profileId: string): Promise<CandidatePreferences | null> {
  try {
    return await get<CandidatePreferences>(`/api/v1/profiles/${profileId}/preferences`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function savePreferences(
  profileId: string,
  input: CandidatePreferencesInput
): Promise<CandidatePreferences> {
  return put<CandidatePreferences>(
    `/api/v1/profiles/${profileId}/preferences`,
    snakeizeKeys(input)
  );
}

// --- Search and applications -------------------------------------------------

/** Ranks jobs already stored by discovery. Performs no outbound requests. */
export async function searchJobs(input: JobSearchInput): Promise<JobSearchResponse> {
  return post<JobSearchResponse>("/api/v1/jobs/search", snakeizeKeys(input));
}

export async function createApplication(input: {
  jobId: string;
  candidateProfileId: string;
  profileVersion: number | null;
}): Promise<Application> {
  return post<Application>("/api/v1/applications", snakeizeKeys(input));
}

export async function getApplication(applicationId: string): Promise<Application> {
  return get<Application>(`/api/v1/applications/${applicationId}`);
}

export async function transitionApplication(
  applicationId: string,
  targetStatus: ApplicationStatus,
  note?: string
): Promise<Application> {
  return post<Application>(`/api/v1/applications/${applicationId}/transition`, {
    target_status: targetStatus,
    note: note ?? null,
  });
}

export async function generatePacket(
  applicationId: string,
  answerKeys: string[] = []
): Promise<GeneratedPacket> {
  return post<GeneratedPacket>(`/api/v1/applications/${applicationId}/materials/generate`, {
    answer_keys: answerKeys,
  });
}

/** The human approval gate: only `approve` is accepted by the initial release. */
export async function approvePacket(applicationId: string, note?: string): Promise<Application> {
  return post<Application>(`/api/v1/applications/${applicationId}/review`, {
    decision: "approve",
    note: note ?? null,
  });
}

// --- Assisted runs (mock ATS sandbox only) -----------------------------------

export async function getBrowserRuns(applicationId: string): Promise<BrowserRun[]> {
  return get<BrowserRun[]>(`/api/v1/applications/${applicationId}/browser-runs`);
}

export async function getBrowserRunLaunchContext(
  applicationId: string
): Promise<BrowserRunLaunchContext> {
  return get<BrowserRunLaunchContext>(
    `/api/v1/applications/${applicationId}/browser-runs/launch-context`
  );
}

export async function startBrowserRun(
  applicationId: string,
  request: BrowserRunStartRequest
): Promise<BrowserRun> {
  return post<BrowserRun>(`/api/v1/applications/${applicationId}/browser-runs`, {
    packet_fingerprint: request.packetFingerprint,
    immutable_inputs: request.immutableInputs,
    approved_fields: request.approvedFields,
    application_url: request.applicationUrl,
    headless: false,
    adapter: request.adapter ?? "greenhouse-like",
  });
}

export async function advanceBrowserRun(
  applicationId: string,
  runId: string,
  steps = 1
): Promise<BrowserRun> {
  return post<BrowserRun>(
    `/api/v1/applications/${applicationId}/browser-runs/${runId}/advance`,
    { steps }
  );
}

export async function pauseBrowserRun(applicationId: string, runId: string): Promise<BrowserRun> {
  return post<BrowserRun>(`/api/v1/applications/${applicationId}/browser-runs/${runId}/pause`);
}

export async function resumeBrowserRun(applicationId: string, runId: string): Promise<BrowserRun> {
  return post<BrowserRun>(`/api/v1/applications/${applicationId}/browser-runs/${runId}/resume`);
}

/**
 * Deliver the approved packet to the in-process MOCK ATS SANDBOX.
 *
 * The API rejects any target that is not a `mock-ats://` sandbox address, and a
 * receipt never advances the application past `stopped_before_submit`.
 */
export async function submitToMockAts(
  applicationId: string,
  runId: string
): Promise<MockAtsReceipt> {
  return post<MockAtsReceipt>(
    `/api/v1/applications/${applicationId}/browser-runs/${runId}/submit-to-mock-ats`
  );
}

export async function listMockAtsReceipts(applicationId: string): Promise<MockAtsReceipt[]> {
  return get<MockAtsReceipt[]>(`/api/v1/applications/${applicationId}/mock-ats-submissions`);
}
