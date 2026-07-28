import { AssistedRunControls } from "./AssistedRunControls";
import type { Metadata } from "next";
import type { ApplicationMaterial, BrowserRun } from "@career-pilot/contracts";
import { camelizeKeys, getBrowserRuns } from "../../../lib/api";

export const metadata: Metadata = { title: "Application materials" };
const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

async function getMaterials(id: string): Promise<ApplicationMaterial[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/applications/${id}/materials`, {
      next: { revalidate: 10 },
    });
    if (!response.ok) return [];
    return camelizeKeys<ApplicationMaterial[]>(await response.json());
  } catch {
    return [];
  }
}

export default async function ApplicationMaterialsPage({
  params,
}: {
  params: { id: string };
}): Promise<JSX.Element> {
  const materials = await getMaterials(params.id);
  const runs: BrowserRun[] = await getBrowserRuns(params.id).catch(() => []);
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Application materials</h1>
        <p className="mt-1 text-sm text-gray-500">
          Review truthful, versioned materials before authorizing the next workflow step.
        </p>
      </div>
      <div className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
        Materials are generated only from profile claims and the immutable job snapshot. CareerPilot
        always stops before final submission.
      </div>
      {materials.length === 0 ? (
        <p className="text-sm text-gray-500">No materials generated yet.</p>
      ) : (
        <div className="space-y-4">
          {materials.map((material) => (
            <section
              key={material.id}
              className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
            >
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  {material.kind === "resume" ? "Tailored résumé" : "Cover letter"}
                </h2>
                <span className="text-xs text-gray-500">
                  Version {material.version} · {material.reviewed ? "Reviewed" : "Needs review"}
                </span>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700">
                {material.content}
              </pre>
              {material.diff ? (
                <details className="mt-4">
                  <summary className="cursor-pointer text-xs font-medium text-blue-700">
                    Show diff
                  </summary>
                  <pre className="mt-2 overflow-auto rounded bg-gray-50 p-3 text-xs">
                    {material.diff}
                  </pre>
                </details>
              ) : null}
              <p className="mt-4 text-xs text-gray-500">
                Source claims: {material.sourceClaims.length}
              </p>
            </section>
          ))}
        </div>
      )}
      <section className="mt-8 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold text-gray-900">Assisted browser runs</h2>
        <p className="mt-1 text-xs text-amber-700">
          Visible/headful only. Every run stops before submit.
        </p>
        {runs.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">No browser runs yet.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {runs.map((run) => (
              <details key={run.id} className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {run.status} · {run.id}
                </summary>
                <p className="mt-2 text-xs text-gray-600">
                  {run.stoppedBeforeSubmit ? "Stopped before submit" : "Awaiting worker"} ·{" "}
                  {run.steps.length} steps · {run.screenshots.length} screenshots
                </p>
                <ul className="mt-2 list-disc pl-5 text-xs text-gray-600">
                  {run.steps.map((step) => (
                    <li key={step.id}>{step.action}</li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        )}
        <AssistedRunControls applicationId={params.id} />
      </section>
    </div>
  );
}
