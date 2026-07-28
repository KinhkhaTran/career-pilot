import type { Metadata } from "next";
import type { JobSummary } from "@career-pilot/contracts";
import { camelizeKeys } from "../../lib/api";

export const metadata: Metadata = { title: "Jobs" };

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

async function getJobs(): Promise<JobSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/jobs`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    return camelizeKeys<JobSummary[]>(await res.json());
  } catch {
    return [];
  }
}

const STATUS_COLORS: Record<string, string> = {
  discovered: "bg-blue-100 text-blue-700",
  normalized: "bg-purple-100 text-purple-700",
  matched: "bg-green-100 text-green-700",
  ignored: "bg-gray-100 text-gray-600",
  expired: "bg-red-100 text-red-600",
};

export default async function JobsPage(): Promise<JSX.Element> {
  const jobs = await getJobs();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Discovered Jobs</h1>
          <p className="mt-1 text-sm text-gray-500">{jobs.length} listings from public ATS feeds</p>
        </div>
      </div>

      {jobs.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <ul className="divide-y divide-gray-200">
            {jobs.map((job) => (
              <li key={job.id} className="px-6 py-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-gray-900 truncate">{job.title}</p>
                    <p className="mt-0.5 text-sm text-gray-500">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ""}
                      {job.isRemote ? " · Remote" : ""}
                    </p>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-gray-100 text-gray-700"}`}
                    >
                      {job.status}
                    </span>
                  </div>
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  Discovered {new Date(job.discoveredAt).toLocaleDateString()}
                </p>
              </li>
            ))}
          </ul>
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
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
      <h3 className="mt-2 text-sm font-semibold text-gray-900">No jobs yet</h3>
      <p className="mt-1 text-sm text-gray-500">
        Job discovery runs on a schedule. Start the worker to populate this list.
      </p>
    </div>
  );
}
