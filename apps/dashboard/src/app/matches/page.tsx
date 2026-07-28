import type { Metadata } from "next";
import type { JobMatch } from "@career-pilot/contracts";
import { camelizeKeys } from "../../lib/api";

export const metadata: Metadata = { title: "Matches" };

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

async function getMatches(): Promise<JobMatch[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/matches?eligible=true`, { next: { revalidate: 30 } });
    if (!response.ok) return [];
    return camelizeKeys<JobMatch[]>(await response.json());
  } catch {
    return [];
  }
}

export default async function MatchesPage(): Promise<JSX.Element> {
  const matches = await getMatches();
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Eligible Matches</h1>
        <p className="mt-1 text-sm text-gray-500">
          Deterministic local scoring with explanations · {matches.length} results
        </p>
      </div>
      {matches.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center text-sm text-gray-500">
          No matches yet. Refresh matching from the API after loading jobs and a candidate profile.
        </div>
      ) : (
        <div className="space-y-4">
          {matches.map((match) => (
            <article key={match.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-gray-900">Job {match.jobId.slice(0, 8)}</h2>
                  <p className="text-xs text-gray-500">Profile v{match.profileVersion} · {match.candidateProfileId.slice(0, 8)}</p>
                </div>
                <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-700">
                  {match.score.toFixed(1)} / 100
                </span>
              </div>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <Explanation label="Skills" value={match.explanation.skills.matched.join(", ") || "No overlap"} />
                <Explanation label="Title" value={match.explanation.title.overlap.join(", ") || "No overlap"} />
                <Explanation label="Education" value={match.explanation.education.matched.join(", ") || "No overlap"} />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function Explanation({ label, value }: { label: string; value: string }): JSX.Element {
  return <div><p className="text-xs font-medium uppercase text-gray-400">{label}</p><p className="mt-1 text-gray-700">{value}</p></div>;
}
