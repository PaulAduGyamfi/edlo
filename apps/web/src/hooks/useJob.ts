import { useEffect, useRef, useState } from "react";

import { getJob, type JobView } from "../api/episodes";

const TERMINAL = new Set(["succeeded", "dead"]);

/**
 * Poll a job until it is done. Backs off 1s → 1.5s → 2.25s, capped at 4s while
 * running and 10s while queued:
 * polling every second forever is pointless load on the API and the database.
 * `onTerminal` fires once, from the poll itself, when the job finishes.
 */
export function useJob(jobId: string | null, onTerminal?: (job: JobView) => void): JobView | null {
  const [job, setJob] = useState<JobView | null>(null);
  const terminal = useRef(onTerminal);
  useEffect(() => {
    terminal.current = onTerminal; // the latest callback, without restarting the poll
  });

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;

    async function poll() {
      if (cancelled) return;
      let latest: JobView;
      try {
        latest = await getJob(jobId as string);
      } catch {
        timer = setTimeout(poll, delay); // a blip; keep polling
        return;
      }
      if (cancelled) return;
      setJob(latest);
      if (TERMINAL.has(latest.status)) {
        terminal.current?.(latest);
        return;
      }
      delay = Math.min(delay * 1.5, latest.status === "running" ? 4000 : 10_000);
      timer = setTimeout(poll, delay);
    }

    timer = setTimeout(poll, delay);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return job;
}
