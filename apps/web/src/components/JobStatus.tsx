import { useEffect, useState } from "react";

import { type JobView } from "../api/episodes";
import { fmtDur, fmtTime } from "../lib/time";

const STALLED_AFTER_S = 20;

const secondsSince = (iso: string, now: number) => Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));

/** "12:30 of 43:10 · about 25m left", from the rate so far. */
function audioProgress(doneMs: number, totalMs: number, runningFor: number): string {
  const through = `${fmtTime(doneMs)} of ${fmtTime(totalMs)}`;
  if (doneMs <= 0 || runningFor < 10) return through;
  const msPerSecond = doneMs / runningFor;
  const left = Math.round((totalMs - doneMs) / msPerSecond);
  return `${through} · about ${fmtDur(Math.max(left, 5))} left`;
}

/**
 * What is happening to a background job, in words a waiting person can act
 * on: how long it has queued, which worker has it, what that worker says it
 * is doing, and a clear hint when nothing has picked it up.
 */
export function JobStatus({ job, doing, hint }: { job: JobView; doing: string; hint?: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const queuedFor = secondsSince(job.created_at, now);
  const runningFor = job.started_at ? secondsSince(job.started_at, now) : 0;
  const p = job.progress ?? {};
  const stalled = job.status === "queued" && queuedFor > STALLED_AFTER_S;
  // A real fraction when the worker reports one (audio done, windows done);
  // otherwise the bar just moves, so "running" is visibly not "stuck".
  const fraction =
    job.status !== "running"
      ? null
      : p.audio_ms
        ? Math.min((p.audio_done_ms ?? 0) / p.audio_ms, 1)
        : p.windows
          ? Math.min((p.windows_done ?? 0) / p.windows, 1)
          : null;
  const percent = fraction === null ? null : Math.round(fraction * 100);

  let line: string;
  if (job.status === "queued") {
    line = `queued ${fmtDur(queuedFor)} ago${job.queue_position && job.queue_position > 1 ? ` · ${job.queue_position - 1} ahead of it` : ""}`;
  } else if (job.status === "running") {
    const stage = p.stage ?? "working";
    const windows = p.windows ? ` · window ${Math.min((p.windows_done ?? 0) + 1, p.windows)} of ${p.windows}` : "";
    const audio = p.audio_ms ? ` · ${audioProgress(p.audio_done_ms ?? 0, p.audio_ms, runningFor)}` : "";
    line = `${stage}${windows}${audio} · ${fmtDur(runningFor)}${job.worker ? ` on ${job.worker}` : ""}${job.attempt > 1 ? ` · attempt ${job.attempt}` : ""}`;
  } else if (job.status === "failed") {
    line = `attempt ${job.attempt} failed${job.error_class ? ` (${job.error_class})` : ""} · it will be retried`;
  } else {
    line = job.status;
  }

  return (
    <div className={`job${stalled ? " job-stalled" : ""}`} role="status" aria-busy="true">
      <span className="tx-pending-dot" aria-hidden="true" />
      <div className="job-body">
        <strong>{job.status === "running" ? doing : job.status === "failed" ? "Retrying…" : "Waiting for a worker…"}</strong>
        <span className="job-line">{line}</span>
        {job.status === "running" && (
          <span className="job-progress">
            <span
              className={`progress${percent === null ? " progress-busy" : ""}`}
              role="progressbar"
              aria-label={doing}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent ?? undefined}
            >
              <i style={percent === null ? undefined : { width: `${percent}%` }} />
            </span>
            {percent !== null && <span className="job-percent">{percent}%</span>}
          </span>
        )}
        {stalled ? (
          <span className="job-hint">
            Nothing has claimed this job for {fmtDur(queuedFor)}. Is a worker running? Locally, <code>scripts/dev.sh</code>{" "}
            starts the whole stack, or run <code>python -m apps.worker.main</code> next to the API.
          </span>
        ) : (
          hint && <span className="tx-pending-sub">{hint}</span>
        )}
      </div>
    </div>
  );
}
