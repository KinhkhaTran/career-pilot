"use client";

/**
 * End-to-end candidate journey, driven entirely by real API calls.
 *
 * SAFETY BOUNDARY
 * ---------------
 * The only submission this panel can perform targets the in-process mock ATS
 * sandbox, labelled MOCK ATS SANDBOX everywhere it appears. The employer URL is
 * rendered as inert text — it is never fetched, opened, or automated — and the
 * API independently rejects any assisted-run target that is not `mock-ats://`.
 */

import { useCallback, useEffect, useState } from "react";
import type {
  Application,
  BrowserRun,
  BrowserRunLaunchContext,
  CandidatePreferences,
  CandidateProfile,
  CandidateProfileInput,
  CandidateProfileSummary,
  GeneratedPacket,
  JobSearchResponse,
  JobSearchResult,
  MockAtsReceipt,
} from "@career-pilot/contracts";
import {
  advanceBrowserRun,
  approvePacket,
  createApplication,
  generatePacket,
  getApplication,
  getBrowserRunLaunchContext,
  getPreferences,
  getProfile,
  listProfiles,
  pauseBrowserRun,
  resumeBrowserRun,
  savePreferences,
  saveProfile,
  searchJobs,
  startBrowserRun,
  submitToMockAts,
  transitionApplication,
} from "../lib/api";

/** Rendered verbatim wherever the sandbox destination is named. */
const MOCK_ATS_LABEL = "MOCK ATS SANDBOX";

interface ProfileForm {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  summary: string;
  skills: string;
}

interface PreferenceForm {
  remoteOnly: boolean;
  allowedLocations: string;
  employmentTypes: string;
  keywords: string;
  minSalary: string;
}

const EMPTY_PROFILE_FORM: ProfileForm = {
  fullName: "",
  email: "",
  phone: "",
  location: "",
  linkedin: "",
  summary: "",
  skills: "",
};

const EMPTY_PREFERENCE_FORM: PreferenceForm = {
  remoteOnly: false,
  allowedLocations: "",
  employmentTypes: "",
  keywords: "",
  minSalary: "",
};

function toList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function profileToForm(profile: CandidateProfile): ProfileForm {
  const contact = profile.contactInfo;
  return {
    fullName: profile.fullName,
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    location: contact?.location ?? "",
    linkedin: contact?.linkedin ?? "",
    summary: profile.summary ?? "",
    skills: profile.skills.join(", "),
  };
}

/**
 * Profiles are append-only, so every field must be written back, not just the
 * edited ones. Untouched sections are carried over from the loaded version.
 */
function formToProfileInput(form: ProfileForm, base: CandidateProfile): CandidateProfileInput {
  return {
    fullName: form.fullName.trim(),
    contactInfo: {
      email: form.email.trim(),
      phone: blankToNull(form.phone),
      location: blankToNull(form.location),
      linkedin: blankToNull(form.linkedin),
      github: base.contactInfo?.github ?? null,
      website: base.contactInfo?.website ?? null,
    },
    summary: blankToNull(form.summary),
    workExperience: base.workExperience,
    education: base.education,
    certifications: base.certifications,
    skills: toList(form.skills),
    languages: base.languages,
  };
}

function preferencesToForm(preferences: CandidatePreferences): PreferenceForm {
  return {
    remoteOnly: preferences.remoteOnly,
    allowedLocations: preferences.allowedLocations.join(", "),
    employmentTypes: preferences.employmentTypes.join(", "),
    keywords: preferences.keywords.join(", "),
    minSalary: preferences.minSalary === null ? "" : String(preferences.minSalary),
  };
}

function percent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function JourneyPanel(): JSX.Element {
  const [profiles, setProfiles] = useState<CandidateProfileSummary[]>([]);
  const [profileId, setProfileId] = useState("");
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [preferenceForm, setPreferenceForm] = useState<PreferenceForm>(EMPTY_PREFERENCE_FORM);

  const [eligibleOnly, setEligibleOnly] = useState(true);
  const [search, setSearch] = useState<JobSearchResponse | null>(null);
  const [selected, setSelected] = useState<JobSearchResult | null>(null);

  const [application, setApplication] = useState<Application | null>(null);
  const [packet, setPacket] = useState<GeneratedPacket | null>(null);
  const [launchContext, setLaunchContext] = useState<BrowserRunLaunchContext | null>(null);
  const [run, setRun] = useState<BrowserRun | null>(null);
  const [receipt, setReceipt] = useState<MockAtsReceipt | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  /** Single place where every action reports progress, success, and failure. */
  const perform = useCallback(
    async (key: string, fallback: string, action: () => Promise<string | null>): Promise<void> => {
      setBusy(key);
      setError(null);
      try {
        const message = await action();
        setNotice(message);
      } catch (caught) {
        setNotice(null);
        setError(errorText(caught, fallback));
      } finally {
        setBusy(null);
      }
    },
    []
  );

  useEffect(() => {
    listProfiles()
      .then((loaded) => {
        setProfiles(loaded);
        const first = loaded[0];
        if (first) setProfileId(first.id);
      })
      .catch((caught: unknown) => setError(errorText(caught, "Unable to load profiles")));
  }, []);

  const loadProfile = useCallback((id: string): void => {
    if (!id) return;
    setSearch(null);
    setSelected(null);
    setApplication(null);
    setPacket(null);
    setLaunchContext(null);
    setRun(null);
    setReceipt(null);
    getProfile(id)
      .then((loaded) => {
        setProfile(loaded);
        setProfileForm(profileToForm(loaded));
      })
      .catch((caught: unknown) => setError(errorText(caught, "Unable to load profile")));
    getPreferences(id)
      .then((loaded) => setPreferenceForm(loaded ? preferencesToForm(loaded) : EMPTY_PREFERENCE_FORM))
      .catch((caught: unknown) => setError(errorText(caught, "Unable to load preferences")));
  }, []);

  useEffect(() => loadProfile(profileId), [profileId, loadProfile]);

  async function handleSave(): Promise<void> {
    const base = profile;
    if (!base) return;
    await perform("save", "Unable to save profile and preferences", async () => {
      const saved = await saveProfile(base.id, formToProfileInput(profileForm, base));
      setProfile(saved);
      setProfileForm(profileToForm(saved));
      const preferences = await savePreferences(base.id, {
        remoteOnly: preferenceForm.remoteOnly,
        allowedLocations: toList(preferenceForm.allowedLocations),
        employmentTypes: toList(preferenceForm.employmentTypes),
        keywords: toList(preferenceForm.keywords),
        minSalary:
          preferenceForm.minSalary.trim() === "" ? null : Number(preferenceForm.minSalary.trim()),
      });
      setPreferenceForm(preferencesToForm(preferences));
      return `Saved profile version ${saved.version} and preferences version ${preferences.version}.`;
    });
  }

  async function handleSearch(): Promise<void> {
    const current = profile;
    if (!current) return;
    await perform("search", "Search failed", async () => {
      const response = await searchJobs({
        profileId: current.id,
        profileVersion: current.version,
        eligibleOnly,
        limit: 25,
      });
      setSearch(response);
      setSelected(null);
      return `Scanned ${response.scanned} stored jobs · ${response.results.length} ranked results.`;
    });
  }

  async function handleCreateApplication(): Promise<void> {
    const current = profile;
    const choice = selected;
    if (!current || !choice) return;
    await perform("application", "Unable to start the application", async () => {
      const created = await createApplication({
        jobId: choice.job.id,
        candidateProfileId: current.id,
        profileVersion: current.version,
      });
      setApplication(created);
      setPacket(null);
      setLaunchContext(null);
      setRun(null);
      setReceipt(null);
      return `Application ${created.id} is at ${created.status}.`;
    });
  }

  async function handlePreparePacket(): Promise<void> {
    const current = application;
    if (!current) return;
    await perform("packet", "Unable to prepare the packet", async () => {
      let state = current;
      if (state.status === "draft") {
        state = await transitionApplication(state.id, "matched", "Selected from preference search");
      }
      const generated = await generatePacket(state.id);
      setPacket(generated);
      const refreshed = await getApplication(state.id);
      setApplication(refreshed);
      return `Packet ${generated.fingerprint.packet_hash.slice(0, 12)} is ready for human review.`;
    });
  }

  async function handleApprove(): Promise<void> {
    const current = application;
    if (!current) return;
    await perform("approve", "Unable to approve the packet", async () => {
      const approved = await approvePacket(current.id, "Reviewed in the dashboard journey panel");
      setApplication(approved);
      const context = await getBrowserRunLaunchContext(approved.id);
      setLaunchContext(context);
      return "Packet approved. The assisted run is now bound to these exact approved inputs.";
    });
  }

  async function handleStartRun(): Promise<void> {
    const current = application;
    const context = launchContext;
    if (!current || !context) return;
    await perform("start", "Unable to start the assisted run", async () => {
      const started = await startBrowserRun(current.id, context);
      setRun(started);
      return `Run queued against the ${MOCK_ATS_LABEL} with ${started.plan.length} planned steps.`;
    });
  }

  async function handleRunAction(
    key: string,
    fallback: string,
    action: (applicationId: string, runId: string) => Promise<BrowserRun>
  ): Promise<void> {
    const current = application;
    const active = run;
    if (!current || !active) return;
    await perform(key, fallback, async () => {
      const updated = await action(current.id, active.id);
      setRun(updated);
      if (updated.status === "stopped_before_submit") {
        const refreshed = await getApplication(current.id);
        setApplication(refreshed);
      }
      return `Run ${updated.status} at step ${updated.cursor} of ${updated.plan.length}.`;
    });
  }

  async function handleSubmitToMockAts(): Promise<void> {
    const current = application;
    const active = run;
    if (!current || !active) return;
    await perform("submit", `Unable to record the ${MOCK_ATS_LABEL} submission`, async () => {
      const recorded = await submitToMockAts(current.id, active.id);
      setReceipt(recorded);
      return `${MOCK_ATS_LABEL} receipt ${recorded.confirmationCode} recorded. No employer was contacted.`;
    });
  }

  const canAdvance = run !== null && (run.status === "queued" || run.status === "running");
  const canPause = canAdvance;
  const canResume = run?.status === "paused";
  const canSubmit = run?.status === "stopped_before_submit" && receipt === null;

  return (
    <section className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-gray-900">Guided journey</h2>
        <p className="mt-1 text-sm text-gray-500">
          Profile → preferences → search → application → packet → assisted run → {MOCK_ATS_LABEL}.
          Every step is a real API call against stored data.
        </p>
      </header>

      {error ? (
        <p className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="mb-4 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          {notice}
        </p>
      ) : null}

      <Step index={1} title="Profile and search preferences">
        <label className="block text-xs font-medium text-gray-600">
          Candidate
          <select
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          >
            {profiles.length === 0 ? <option value="">No stored profiles</option> : null}
            {profiles.map((item) => (
              <option key={item.id} value={item.id}>
                {item.fullName} · v{item.version}
              </option>
            ))}
          </select>
        </label>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            label="Full name"
            value={profileForm.fullName}
            onChange={(value) => setProfileForm({ ...profileForm, fullName: value })}
          />
          <Field
            label="Email"
            value={profileForm.email}
            onChange={(value) => setProfileForm({ ...profileForm, email: value })}
          />
          <Field
            label="Phone"
            value={profileForm.phone}
            onChange={(value) => setProfileForm({ ...profileForm, phone: value })}
          />
          <Field
            label="Location"
            value={profileForm.location}
            onChange={(value) => setProfileForm({ ...profileForm, location: value })}
          />
          <Field
            label="LinkedIn"
            value={profileForm.linkedin}
            onChange={(value) => setProfileForm({ ...profileForm, linkedin: value })}
          />
          <Field
            label="Skills (comma separated)"
            value={profileForm.skills}
            onChange={(value) => setProfileForm({ ...profileForm, skills: value })}
          />
        </div>
        <label className="mt-3 block text-xs font-medium text-gray-600">
          Summary
          <textarea
            value={profileForm.summary}
            onChange={(event) => setProfileForm({ ...profileForm, summary: event.target.value })}
            rows={3}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            label="Allowed locations (comma separated)"
            value={preferenceForm.allowedLocations}
            onChange={(value) => setPreferenceForm({ ...preferenceForm, allowedLocations: value })}
          />
          <Field
            label="Employment types (comma separated)"
            value={preferenceForm.employmentTypes}
            onChange={(value) => setPreferenceForm({ ...preferenceForm, employmentTypes: value })}
          />
          <Field
            label="Keywords (comma separated)"
            value={preferenceForm.keywords}
            onChange={(value) => setPreferenceForm({ ...preferenceForm, keywords: value })}
          />
          <Field
            label="Minimum salary"
            value={preferenceForm.minSalary}
            onChange={(value) => setPreferenceForm({ ...preferenceForm, minSalary: value })}
          />
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={preferenceForm.remoteOnly}
            onChange={(event) =>
              setPreferenceForm({ ...preferenceForm, remoteOnly: event.target.checked })
            }
          />
          Remote only (hard eligibility constraint)
        </label>

        <Action
          label="Save profile and preferences"
          busyLabel="Saving…"
          onClick={handleSave}
          disabled={profile === null}
          busy={busy === "save"}
        />
        {profile ? (
          <p className="mt-2 text-xs text-gray-500">
            Editing appends a new version — earlier versions stay readable, so an approved packet
            keeps resolving. Current: v{profile.version}.
          </p>
        ) : null}
      </Step>

      <Step index={2} title="Search stored jobs">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={eligibleOnly}
            onChange={(event) => setEligibleOnly(event.target.checked)}
          />
          Eligible results only
        </label>
        <Action
          label="Search jobs"
          busyLabel="Searching…"
          onClick={handleSearch}
          disabled={profile === null}
          busy={busy === "search"}
        />
        {search ? (
          <>
            <p className="mt-3 text-xs text-gray-500">
              Ranked against preferences v{search.preferences.version} · scanned {search.scanned} ·
              filtered out {search.filteredOut}. Search reads stored jobs only and never contacts an
              employer.
            </p>
            <ul className="mt-3 divide-y divide-gray-100 rounded-md border border-gray-200">
              {search.results.map((result) => (
                <li
                  key={result.job.id}
                  className="flex items-center justify-between gap-3 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">{result.job.title}</p>
                    <p className="truncate text-xs text-gray-500">
                      {result.job.company} · {result.job.location ?? "Location unstated"} ·{" "}
                      {result.job.isRemote ? "Remote" : "On-site"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-sm font-semibold text-indigo-700">
                      {percent(result.match.score)}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelected(result)}
                      className={[
                        "rounded-md px-3 py-1.5 text-xs font-medium",
                        selected?.job.id === result.job.id
                          ? "bg-indigo-600 text-white"
                          : "border border-indigo-600 text-indigo-700",
                      ].join(" ")}
                    >
                      {selected?.job.id === result.job.id ? "Selected" : "Select"}
                    </button>
                  </div>
                </li>
              ))}
              {search.results.length === 0 ? (
                <li className="px-3 py-2 text-sm text-gray-500">
                  No stored job met these preferences.
                </li>
              ) : null}
            </ul>
          </>
        ) : null}
      </Step>

      <Step index={3} title="Match explanation">
        {selected ? (
          <div className="rounded-md border border-gray-200 bg-gray-50 p-4">
            <p className="text-sm font-medium text-gray-900">
              {selected.job.title} · {selected.job.company}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Score {percent(selected.match.score)} ·{" "}
              {selected.match.eligible ? "Eligible" : "Not eligible"} · profile v
              {selected.match.profileVersion} · fingerprint{" "}
              {selected.match.inputFingerprint.slice(0, 12)}
            </p>
            <p className="mt-1 break-all text-xs text-gray-500">
              Employer posting (reference only, never automated): {selected.sourceUrl}
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-gray-700">
              {selected.match.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-gray-600 sm:grid-cols-4">
              <Factor
                label="Skills"
                ratio={selected.match.explanation.skills.ratio}
                weight={selected.match.explanation.weights.skills}
                detail={selected.match.explanation.skills.matched.join(", ")}
              />
              <Factor
                label="Title"
                ratio={selected.match.explanation.title.ratio}
                weight={selected.match.explanation.weights.title}
                detail={selected.match.explanation.title.overlap.join(", ")}
              />
              <Factor
                label="Experience"
                ratio={selected.match.explanation.experience.ratio}
                weight={selected.match.explanation.weights.experience}
                detail={selected.match.explanation.experience.overlap.join(", ")}
              />
              <Factor
                label="Education"
                ratio={selected.match.explanation.education.ratio}
                weight={selected.match.explanation.weights.education}
                detail={selected.match.explanation.education.matched.join(", ")}
              />
            </dl>
            <Action
              label="Start application for this job"
              busyLabel="Starting…"
              onClick={handleCreateApplication}
              disabled={false}
              busy={busy === "application"}
            />
          </div>
        ) : (
          <p className="text-sm text-gray-500">Select a search result to see why it scored.</p>
        )}
      </Step>

      <Step index={4} title="Prepare and approve the packet">
        {application ? (
          <>
            <p className="text-sm text-gray-700">
              Application <span className="font-mono text-xs">{application.id}</span> · status{" "}
              <span className="font-medium">{application.status}</span>
            </p>
            <div className="flex flex-wrap gap-3">
              <Action
                label="Prepare packet"
                busyLabel="Generating…"
                onClick={handlePreparePacket}
                disabled={application.status !== "draft" && application.status !== "matched"}
                busy={busy === "packet"}
              />
              <Action
                label="Approve reviewed packet"
                busyLabel="Approving…"
                onClick={handleApprove}
                disabled={application.status !== "human_review"}
                busy={busy === "approve"}
              />
            </div>
            {packet ? (
              <div className="mt-3 space-y-3">
                <p className="text-xs text-gray-500">
                  Packet hash {packet.fingerprint.packet_hash.slice(0, 16)} · résumé v
                  {packet.resume.version} · cover letter v{packet.coverLetter.version}
                </p>
                <Excerpt title="Tailored résumé" content={packet.resume.content} />
                <Excerpt title="Cover letter" content={packet.coverLetter.content} />
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-gray-500">Start an application first.</p>
        )}
      </Step>

      <Step index={5} title={`Assisted run against the ${MOCK_ATS_LABEL}`}>
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
            {MOCK_ATS_LABEL}
          </p>
          <p className="mt-1 text-xs text-amber-800">
            The assisted run drives the in-process sandbox board only. The plan contains no submit
            action, so it always terminates at <code>stopped_before_submit</code>, and no employer
            site is ever opened or filled.
          </p>
        </div>
        {launchContext ? (
          <p className="mt-3 break-all text-xs text-gray-500">
            Sandbox target: <code>{launchContext.applicationUrl}</code> · {" "}
            {launchContext.plannedSteps.length} planned steps · approved fields:{" "}
            {Object.keys(launchContext.approvedFields).join(", ")}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Action
            label={`Start ${MOCK_ATS_LABEL} run`}
            busyLabel="Starting…"
            onClick={handleStartRun}
            disabled={launchContext === null || run !== null}
            busy={busy === "start"}
          />
          <Action
            label="Advance one step"
            busyLabel="Advancing…"
            onClick={() =>
              handleRunAction("advance", "Unable to advance the run", (appId, runId) =>
                advanceBrowserRun(appId, runId, 1)
              )
            }
            disabled={!canAdvance}
            busy={busy === "advance"}
          />
          <Action
            label="Pause"
            busyLabel="Pausing…"
            onClick={() =>
              handleRunAction("pause", "Unable to pause the run", pauseBrowserRun)
            }
            disabled={!canPause}
            busy={busy === "pause"}
          />
          <Action
            label="Resume"
            busyLabel="Resuming…"
            onClick={() =>
              handleRunAction("resume", "Unable to resume the run", resumeBrowserRun)
            }
            disabled={!canResume}
            busy={busy === "resume"}
          />
        </div>
        {run ? (
          <div className="mt-3">
            <p className="text-sm text-gray-700">
              Run <span className="font-mono text-xs">{run.id}</span> · {run.status} · step{" "}
              {run.cursor} of {run.plan.length}
            </p>
            <ol className="mt-2 space-y-1 text-xs text-gray-600">
              {run.plan.map((step, index) => (
                <li key={`${step.action}-${String(index)}`}>
                  <span className={index < run.cursor ? "text-green-700" : "text-gray-400"}>
                    {index < run.cursor ? "done" : "pending"}
                  </span>{" "}
                  · {step.action}
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </Step>

      <Step index={6} title={`Submit to ${MOCK_ATS_LABEL}`}>
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
            {MOCK_ATS_LABEL}
          </p>
          <p className="mt-1 text-xs text-amber-800">
            This records the approved packet against the local sandbox board. It reaches no employer
            and leaves the application at <code>stopped_before_submit</code>.
          </p>
        </div>
        <Action
          label={`Submit to ${MOCK_ATS_LABEL}`}
          busyLabel="Recording…"
          onClick={handleSubmitToMockAts}
          disabled={!canSubmit}
          busy={busy === "submit"}
        />
        {receipt ? (
          <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
            <p className="font-semibold uppercase tracking-wide text-amber-900">
              {MOCK_ATS_LABEL} receipt
            </p>
            <p className="mt-1">
              Confirmation {receipt.confirmationCode} · board {receipt.boardToken} · job{" "}
              {receipt.externalJobId}
            </p>
            <p className="mt-1">Fields delivered: {Object.keys(receipt.payload).join(", ")}</p>
          </div>
        ) : null}
      </Step>
    </section>
  );
}

function Step({
  index,
  title,
  children,
}: {
  index: number;
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="border-t border-gray-100 py-5 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">
        <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
          {index}
        </span>
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label className="block text-xs font-medium text-gray-600">
      {label}
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900"
      />
    </label>
  );
}

function Action({
  label,
  busyLabel,
  onClick,
  disabled,
  busy,
}: {
  label: string;
  busyLabel: string;
  onClick: () => void | Promise<void>;
  disabled: boolean;
  busy: boolean;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => void onClick()}
      disabled={disabled || busy}
      className="mt-3 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
    >
      {busy ? busyLabel : label}
    </button>
  );
}

function Factor({
  label,
  ratio,
  weight,
  detail,
}: {
  label: string;
  ratio: number;
  weight: number;
  detail: string;
}): JSX.Element {
  return (
    <div>
      <dt className="font-medium text-gray-800">
        {label} · {percent(ratio)}
      </dt>
      <dd className="text-gray-500">
        weight {percent(weight)}
        {detail ? ` · ${detail}` : ""}
      </dd>
    </div>
  );
}

function Excerpt({ title, content }: { title: string; content: string }): JSX.Element {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
      <p className="text-xs font-semibold text-gray-800">{title}</p>
      <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap font-sans text-xs text-gray-700">
        {content}
      </pre>
    </div>
  );
}
