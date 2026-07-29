import Link from "next/link";
import type { Metadata } from "next";
import { JourneyPanel } from "./JourneyPanel";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage(): JSX.Element {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          CareerPilot · Initial release · Always stops before submission
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <SummaryCard
          title="Jobs Discovered"
          value="10"
          href="/jobs"
          description="Public listings normalized from ATS feeds"
        />
        <SummaryCard
          title="Active Applications"
          value="3"
          href="/applications"
          description="In progress — awaiting human review"
        />
        <SummaryCard
          title="Pending Authorization"
          value="1"
          href="/applications"
          description="Stopped before submission — requires explicit gate"
        />
      </div>

      <JourneyPanel />

      <div className="mt-8 rounded-lg border border-amber-200 bg-amber-50 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-amber-800">Initial Release Boundary</h3>
            <p className="mt-1 text-sm text-amber-700">
              This release stops before final submission. No application is submitted without explicit human authorization in a future release.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  href,
  description,
}: {
  title: string;
  value: string;
  href: string;
  description: string;
}): JSX.Element {
  return (
    <Link
      href={href}
      className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all"
    >
      <dt className="text-sm font-medium text-gray-500 truncate">{title}</dt>
      <dd className="mt-1 text-3xl font-bold tracking-tight text-gray-900">{value}</dd>
      <p className="mt-2 text-sm text-gray-500">{description}</p>
    </Link>
  );
}
