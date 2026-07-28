"use client";

import { useEffect, useState } from "react";
import type { BrowserRun, BrowserRunLaunchContext } from "@career-pilot/contracts";
import { getBrowserRunLaunchContext, startBrowserRun } from "../../../lib/api";

export function AssistedRunControls({ applicationId }: { applicationId: string }): JSX.Element {
  const [context, setContext] = useState<BrowserRunLaunchContext | null>(null);
  const [run, setRun] = useState<BrowserRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getBrowserRunLaunchContext(applicationId)
      .then(setContext)
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : "Launch context unavailable")
      );
  }, [applicationId]);

  async function handleStart(): Promise<void> {
    if (!context) return;
    setBusy(true);
    setMessage(null);
    try {
      setRun(await startBrowserRun(applicationId, context));
      setMessage(
        "Queued for a visible, human-supervised browser run. Final submission remains manual."
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to start assisted run");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleStart}
          disabled={!context || busy}
          className="rounded-md bg-blue-700 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Starting…" : "Run visible assisted fill"}
        </button>
        {context ? (
          <a
            href={context.applicationUrl}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-blue-700 px-3 py-2 text-sm font-medium text-blue-700"
          >
            Open employer form manually
          </a>
        ) : null}
      </div>
      <p className="mt-3 text-xs text-blue-900">
        Uses the approved résumé packet and fills only reviewed fields. CareerPilot never clicks
        final submit.
      </p>
      {run ? (
        <p className="mt-2 text-xs text-blue-900">
          Run {run.id}: {run.status}
        </p>
      ) : null}
      {message ? <p className="mt-2 text-xs text-gray-700">{message}</p> : null}
    </div>
  );
}
