import type { Metadata } from "next";
import type { CandidateProfile } from "@career-pilot/contracts";
import { camelizeKeys } from "../../lib/api";

export const metadata: Metadata = { title: "Profile" };

const API_BASE = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://localhost:8000";

// The list endpoint returns only a lightweight summary; the full profile
// (contact, summary, skills, experience) lives on the detail endpoint.
async function getProfile(): Promise<CandidateProfile | null> {
  try {
    const listRes = await fetch(`${API_BASE}/api/v1/profiles`, { next: { revalidate: 60 } });
    if (!listRes.ok) return null;
    const summaries = camelizeKeys<Array<{ id: string }>>(await listRes.json());
    const first = summaries[0];
    if (!first) return null;

    const detailRes = await fetch(`${API_BASE}/api/v1/profiles/${first.id}`, {
      next: { revalidate: 60 },
    });
    if (!detailRes.ok) return null;

    // The API nests contact under `contactInfo`; the contract calls it `contact`.
    const { contactInfo, ...rest } = camelizeKeys<Record<string, unknown>>(await detailRes.json());
    return { ...rest, contact: contactInfo ?? {} } as unknown as CandidateProfile;
  } catch {
    return null;
  }
}

export default async function ProfilePage(): Promise<JSX.Element> {
  const profile = await getProfile();

  if (!profile) {
    return (
      <div className="text-center py-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Candidate Profile</h1>
        <p className="text-sm text-gray-500">
          No profile loaded. Run seed data or create a profile.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{profile.fullName}</h1>
          <p className="mt-1 text-sm text-gray-500">
            Profile version {profile.version}
            {profile.updatedAt
              ? ` · Updated ${new Date(profile.updatedAt).toLocaleDateString()}`
              : ""}
          </p>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
          v{profile.version}
        </span>
      </div>

      <div className="space-y-6">
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
            Contact
          </h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-gray-500">Email</dt>
              <dd className="text-gray-900">{profile.contactInfo?.email ?? "—"}</dd>
            </div>
            {profile.contactInfo?.location ? (
              <div>
                <dt className="text-gray-500">Location</dt>
                <dd className="text-gray-900">{profile.contactInfo.location}</dd>
              </div>
            ) : null}
            {profile.contactInfo?.linkedin ? (
              <div className="col-span-2">
                <dt className="text-gray-500">LinkedIn</dt>
                <dd className="text-gray-900 truncate">{profile.contactInfo.linkedin}</dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
            Summary
          </h2>
          <p className="text-sm text-gray-700 leading-relaxed">{profile.summary}</p>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
            Skills
          </h2>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200"
              >
                {skill}
              </span>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
            Work Experience
          </h2>
          <div className="space-y-4">
            {profile.workExperience.map((exp, index) => (
              <div key={index} className="border-l-2 border-indigo-200 pl-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{exp.title}</p>
                    <p className="text-sm text-gray-600">{exp.company}</p>
                  </div>
                  <p className="text-xs text-gray-400 whitespace-nowrap ml-4">
                    {exp.startDate} &ndash; {exp.isCurrent ? "Present" : (exp.endDate ?? "")}
                  </p>
                </div>
                <p className="mt-1 text-sm text-gray-600">{exp.description}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
