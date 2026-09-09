import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { type EpisodeSummary, getHistory, listEpisodes } from "../api/episodes";
import { type Episode, EpisodesContext, stageFromHistory } from "../state/episodes";

const REFRESH_MS = 30_000;
// How old the data may be before the UI says so.
const STALE_AFTER_MS = 90_000;

async function withHistory(summary: EpisodeSummary): Promise<Episode> {
  try {
    const history = await getHistory(summary.id);
    return { ...summary, stage: stageFromHistory(history), history, historyError: null };
  } catch (e) {
    return { ...summary, stage: null, history: null, historyError: toApiError(e) };
  }
}

export function EpisodesProvider({ children }: { children: ReactNode }) {
  const [episodes, setEpisodes] = useState<Episode[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  // Render-time clock, advanced by the refresh timer, so staleness is derived
  // from state rather than from Date.now() during render.
  const [now, setNow] = useState(() => Date.now());
  const inFlight = useRef<Promise<void> | null>(null);

  const reload = useCallback(() => {
    if (inFlight.current) return inFlight.current;
    setLoading(true);
    const run = (async () => {
      try {
        const summaries = await listEpisodes();
        const full = await Promise.all(summaries.map(withHistory));
        setEpisodes(full);
        setUpdatedAt(new Date());
        setError(null);
      } catch (e) {
        setError(toApiError(e));
      } finally {
        setLoading(false);
        inFlight.current = null;
      }
    })();
    inFlight.current = run;
    return run;
  }, []);

  useEffect(() => {
    void reload();
    const timer = setInterval(() => {
      setNow(Date.now());
      void reload();
    }, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void reload();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [reload]);

  const patch = useCallback((summary: EpisodeSummary, extra: Partial<Episode> = {}) => {
    setEpisodes((all) => {
      const base: Episode = { stage: "registered", history: [], historyError: null, ...summary };
      if (!all) return [{ ...base, ...extra }];
      const i = all.findIndex((e) => e.id === summary.id);
      if (i === -1) return [...all, { ...base, ...extra }];
      const next = all.slice();
      next[i] = { ...all[i], ...summary, ...extra };
      return next;
    });
  }, []);

  const stale = updatedAt !== null && now - updatedAt.getTime() > STALE_AFTER_MS;

  const value = useMemo(
    () => ({ episodes, error, loading, updatedAt, stale, reload, patch }),
    [episodes, error, loading, updatedAt, stale, reload, patch],
  );

  return <EpisodesContext.Provider value={value}>{children}</EpisodesContext.Provider>;
}
