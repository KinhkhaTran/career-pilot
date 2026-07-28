import type { Metadata } from "next";
import type { ApplicationSummary } from "@career-pilot/contracts";
import { APPLICATION_STATUS_LABELS } from "@career-pilot/contracts";
import { camelizeKeys } from "../../lib/api";

export const metadata: Metadata = { title: "Applications" };

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

async function getApplications(): Promise<ApplicationSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/applications`, { next: { revalidate: 30 } });
    if (!res.ok) return [];
    return camelizeKeys<ApplicationSummary[]>(await res.json());
  } catch {
    return [];
  }
}

const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  matched: "bg-blue-100 text-blue-700",
  packet_draft: "bg-blue-100 text-blue-800",
  packet_ready: "bg-purple-100 text-purple-700",
  human_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-700",
  stopped_before_submit: "bg-amber-100 text-amber-800",
  submitted: "bg-emerald-100 text-emerald-800",
};

export default async function ApplicationsPage(): Promise<JSX.Element> {
  const applications = await getApplications();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
        <p className="mt-1 text-sm text-gray-500">
          Track the status of your assisted application packets
        </p>
      </div>

      <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3">
        <p className="text-xs text-amber-800">
          <strong>Initial release:</strong> All applications stop at &ldquo;Pending Authorization&rdquo; before
          submission. Final submission requires explicit human authorization in a future release.
        </p>
      </div>

      {applications.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <p className="text-sm text-gray-500">
            No applications yet. Discover and match jobs to get started.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Application
                </th>
                <th
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Status
                </th>
                <th
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Created
                </th>
                <th
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {applications.map((app) => (
                <tr key={app.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {app.id.slice(0, 8)}&hellip;
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE_CLASSES[app.status] ?? "bg-gray-100 text-gray-700"}`}
                    >
                      {APPLICATION_STATUS_LABELS[app.status] ?? app.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(app.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(app.updatedAt).toLocaleDateString()}
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
