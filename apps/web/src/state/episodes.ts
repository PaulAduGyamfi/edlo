import { createContext, useContext } from "react";

import { type ApiError } from "../api/client";
import { type EpisodeSummary, type Stage, type Transition } from "../api/episodes";

/**
 * The list endpoint does not include the stage, so each episode's history
 * is fetched alongside it and the stage is read off the last transition.
 */
export type Episode = EpisodeSummary & {
  stage: Stage | null; // null when the history could not be loaded
  history: Transition[] | null;
  historyError: ApiError | null;
};

export type EpisodesApi = {
  episodes: Episode[] | null; // null until the first successful load
  error: ApiError | null; // last load failure, kept alongside stale data
  loading: boolean;
  updatedAt: Date | null;
  stale: boolean;
  reload: () => Promise<void>;
  /** Merge a fresh summary from a write response without waiting for a reload. */
  patch: (summary: EpisodeSummary, extra?: Partial<Episode>) => void;
};

export const EpisodesContext = createContext<EpisodesApi | null>(null);

export function useEpisodes(): EpisodesApi {
  const ctx = useContext(EpisodesContext);
  if (!ctx) throw new Error("useEpisodes must be used inside EpisodesProvider");
  return ctx;
}

export function stageFromHistory(history: Transition[]): Stage {
  return history.length ? history[history.length - 1].to : "registered";
}
