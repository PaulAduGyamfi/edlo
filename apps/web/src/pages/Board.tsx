import { useCallback, useEffect, useState } from "react";

import { api, isApiError, type ApiError } from "../api/client";
import { Banner } from "../components/Banner";
import { BoardSkeleton } from "../components/BoardSkeleton";
import { EmptyState } from "../components/EmptyState";
import { ErrorPanel } from "../components/ErrorPanel";

type Episode = {
  id: string;
  title: string;
  recorded_on: string;
  publish_on: string | null;
  days_remaining: number | null;
  schedule_status: "on_track" | "due_soon" | "overdue" | "published" | null;
  stage: string;
};

const STAGES = [
  "registered",
  "mixing",
  "plan_ready",
  "editing",
  "review",
  "published",
];

export function Board() {
  const [episodes, setEpisodes] = useState<Episode[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      setEpisodes(await api<Episode[]>("/episodes"));
      setUpdatedAt(new Date());
      setError(null);
    } catch (e) {
      if (isApiError(e)) setError(e);
      else throw e;
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  if (error) return <ErrorPanel error={error} onRetry={load} />;
  if (!episodes) return <BoardSkeleton />;
  if (episodes.length === 0) return <EmptyState onCreate={load} />;

  const stale = updatedAt && Date.now() - updatedAt.getTime() > 90_000;

  return (
    <div className="board">
      {stale && (
        <Banner kind="warn">
          Showing data from {updatedAt.toLocaleTimeString()}
        </Banner>
      )}
      <div className="columns">
        {STAGES.map((stage) => (
          <section key={stage} className="column">
            <h2>{stage.replace("_", " ")}</h2>
            {episodes
              .filter((e) => e.stage === stage)
              .map((e) => (
                <EpisodeCard key={e.id} episode={e} onChange={load} />
              ))}
          </section>
        ))}
      </div>
    </div>
  );
}

// onChange is accepted but not used yet — the card has no controls to
// trigger a refresh with.
function EpisodeCard({
  episode,
}: {
  episode: Episode;
  onChange: () => void;
}) {
  // The countdown is the whole intervention: an episode without a visible
  // date is an episode nobody feels responsible for.
  const tone = episode.schedule_status ?? "none";
  const days = episode.days_remaining;

  return (
    <article className={`card tone-${tone}`}>
      <h3>{episode.title}</h3>
      {episode.publish_on && days !== null ? (
        <p className="countdown">
          {days < 0
            ? `${Math.abs(days)} days overdue`
            : `${days} days to publish`}
          <span className="date"> · {episode.publish_on}</span>
        </p>
      ) : (
        <p className="countdown none">No posting date</p>
      )}
    </article>
  );
}