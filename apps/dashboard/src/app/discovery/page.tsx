import type { Metadata } from "next";
import type { DiscoveryRunSummary } from "@career-pilot/contracts";

export const metadata: Metadata = { title: "Discovery Runs" };

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

async function getDiscoveryRuns(): Promise<DiscoveryRunSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/discovery/runs`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return [];
    return res.json() as Promise<DiscoveryRunSummary[]>;
  } catch {
    return [];
  }
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-600",
};

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return "—";
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m`;
}

export default async function DiscoveryPage(): Promise<JSX.Element> {
  const runs = await getDiscoveryRuns();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Discovery Runs</h1>
        <p className="mt-1 text-sm text-gray-500">
          Scheduled job discovery from Greenhouse, Lever, and Ashby public boards.
        </p>
      </div>

      {runs.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source / Company
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Jobs
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Started
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 capitalize">
                      {run.source}
                    </div>
                    <div className="text-sm text-gray-500">{run.companyId}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[run.status] ?? "bg-gray-100 text-gray-700"}`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    <span className="font-medium">{run.jobsDiscovered}</span> found
                    {run.jobsUpserted > 0 && (
                      <span className="ml-2 text-green-600">+{run.jobsUpserted} new</span>
                    )}
                    {run.jobsSkipped > 0 && (
                      <span className="ml-2 text-gray-400">{run.jobsSkipped} unchanged</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDuration(run.startedAt, run.completedAt)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    {run.startedAt
                      ? new Date(run.startedAt).toLocaleString()
                      : run.createdAt
                        ? new Date(run.createdAt).toLocaleString()
                        : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div className="text-center py-16 bg-white rounded-lg border border-gray-200">
      <svg
        className="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1}
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
        />
      </svg>
      <h3 className="mt-2 text-sm font-semibold text-gray-900">No discovery runs yet</h3>
      <p className="mt-1 text-sm text-gray-500">
        Discovery runs automatically on a schedule. Start the ARQ worker to begin.
      </p>
    </div>
  );
}
