const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/**
 * The API serializes JSON in snake_case (Pydantic default); the shared
 * `@career-pilot/contracts` types are camelCase. Recursively rewrite object
 * keys so wire payloads conform to the contracts. Values are left untouched.
 */
import type {
  BrowserRun,
  BrowserRunLaunchContext,
  BrowserRunStartRequest,
} from "@career-pilot/contracts";

export async function getBrowserRuns(applicationId: string): Promise<BrowserRun[]> {
  const payload = await apiFetch<unknown>(`/api/v1/applications/${applicationId}/browser-runs`);
  return camelizeKeys<BrowserRun[]>(payload);
}

export async function getBrowserRunLaunchContext(
  applicationId: string
): Promise<BrowserRunLaunchContext> {
  const payload = await apiFetch<unknown>(
    `/api/v1/applications/${applicationId}/browser-runs/launch-context`
  );
  return camelizeKeys<BrowserRunLaunchContext>(payload);
}

export async function startBrowserRun(
  applicationId: string,
  request: BrowserRunStartRequest
): Promise<BrowserRun> {
  const payload = await apiFetch<unknown>(`/api/v1/applications/${applicationId}/browser-runs`, {
    method: "POST",
    body: JSON.stringify({
      packet_fingerprint: request.packetFingerprint,
      immutable_inputs: request.immutableInputs,
      approved_fields: request.approvedFields,
      application_url: request.applicationUrl,
      headless: false,
      adapter: request.adapter ?? "greenhouse-like",
    }),
  });
  return camelizeKeys<BrowserRun>(payload);
}

export function camelizeKeys<T = unknown>(input: unknown): T {
  if (Array.isArray(input)) {
    return input.map((item) => camelizeKeys(item)) as T;
  }
  if (input !== null && typeof input === "object") {
    return Object.fromEntries(
      Object.entries(input as Record<string, unknown>).map(([key, value]) => [
        key.replace(/_([a-z0-9])/g, (_, char: string) => char.toUpperCase()),
        camelizeKeys(value),
      ])
    ) as T;
  }
  return input as T;
}
