import { type FormEvent, useState } from "react";

import { toApiError, type ApiError } from "../api/client";
import { deleteEpisode } from "../api/episodes";
import { AudioPanel } from "../components/AudioPanel";
import { Banner } from "../components/Banner";
import { Dialog } from "../components/Dialog";
import { ErrorDetail } from "../components/ErrorDetail";
import { ErrorPanel } from "../components/ErrorPanel";
import { HistoryList } from "../components/HistoryList";
import { SlotCalendar } from "../components/SlotCalendar";
import { StagePanel } from "../components/StagePanel";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { STAGE_LABEL } from "../domain/workflow";
import { fmtDate, fmtDateLong } from "../lib/dates";
import { type Episode, useEpisodes } from "../state/episodes";
import { useMe, useSession } from "../state/session";
import { useToast } from "../state/toast";
import { Shell, Tabs, Who } from "./Shell";
import { type Go } from "./nav";

import "../styles/session.css";
import "../styles/episode.css";

export function EpisodeScreen({ id, go }: { id: string; go: Go }) {
  const me = useMe();
  const { signOut } = useSession();
  const { episodes, error, stale, updatedAt, reload } = useEpisodes();
  const episode = episodes?.find((e) => e.id === id);

  let body;
  if (!episodes && error) {
    body = <ErrorPanel error={error} onRetry={() => void reload()} />;
  } else if (!episodes) {
    body = <div className="hero hero-skeleton" aria-busy="true" />;
  } else if (!episode) {
    body = (
      <div className="error-panel">
        <h2>Episode not found</h2>
        <p>Nothing on the board has that id. It may have been removed, or the link is wrong.</p>
        <button type="button" onClick={() => go({ screen: "schedule" })}>
          Back to the schedule
        </button>
      </div>
    );
  } else {
    body = <EpisodeBody episode={episode} go={go} />;
  }

  return (
    <Shell
      go={go}
      center={<Tabs route={{ screen: "episode", id }} go={go} episodeTitle={episode?.title} />}
      right={<Who me={me} onSignOut={() => signOut()} />}
    >
      <main className="page">
        {episodes && error && (
          <Banner kind="error">
            <ErrorDetail error={error} lead="Couldn't refresh." onRetry={() => void reload()} />
          </Banner>
        )}
        {episodes && !error && stale && updatedAt && (
          <Banner kind="warn">Showing data from {updatedAt.toLocaleTimeString()}.</Banner>
        )}
        {body}
      </main>
    </Shell>
  );
}

function Countdown({ episode }: { episode: Episode }) {
  const days = episode.days_remaining;
  if (episode.stage === "published") {
    return (
      <div className="countdown">
        <span className="countdown-n countdown-done">✓</span>
        <span className="countdown-label">Published</span>
        {episode.publish_on && <span className="countdown-date">{fmtDateLong(episode.publish_on)}</span>}
      </div>
    );
  }
  if (episode.publish_on === null || days === null) {
    return (
      <div className="countdown">
        <span className="countdown-n countdown-none">—</span>
        <span className="countdown-label">No posting date</span>
        <span className="countdown-date">Pick one on the calendar below.</span>
      </div>
    );
  }
  const tone = episode.schedule_status ?? "on_track";
  return (
    <div className={`countdown countdown-${tone}`}>
      <span className="countdown-n">{Math.abs(days)}</span>
      <span className="countdown-label">
        {days < 0 ? `Day${days === -1 ? "" : "s"} overdue` : days === 0 ? "Publishes today" : `Day${days === 1 ? "" : "s"} to publish`}
      </span>
      <span className="countdown-date">{fmtDateLong(episode.publish_on)}</span>
    </div>
  );
}

function EpisodeBody({ episode, go }: { episode: Episode; go: Go }) {
  const { reload } = useEpisodes();
  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">
            Recorded {fmtDate(episode.recorded_on)}
            {episode.stage && (
              <>
                {" · "}
                <span className={`stage-chip stage-${episode.stage}`}>{STAGE_LABEL[episode.stage]}</span>
              </>
            )}
          </p>
          <h1 className="display-xl hero-title">{episode.title}</h1>
        </div>
        <Countdown episode={episode} />
      </section>

      <div className="ep-layout">
        <div className="ep-main">
          <section className="panel">
            <header className="panel-head">
              <h2 className="display-md">Stage</h2>
              <span className="sec-sub">Every move is recorded with who made it and why.</span>
            </header>
            <StagePanel episode={episode} onMoved={() => void reload()} />
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2 className="display-md">Audio</h2>
              <span className="sec-sub">Rough for the plan, final for the cut.</span>
            </header>
            <AudioPanel episode={episode} />
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2 className="display-md">Transcript</h2>
              <span className="sec-sub">Timecoded from the rough mix. Drag the timeline, or search.</span>
            </header>
            <TranscriptPanel key={episode.id} episodeId={episode.id} />
          </section>
        </div>

        <aside className="ep-side">
          <section className="panel">
            <header className="panel-head">
              <h2 className="display-md">Posting slot</h2>
              <span className="sec-sub">One episode per date.</span>
            </header>
            <SlotCalendar episode={episode} />
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2 className="display-md">History</h2>
              <span className="sec-sub">Newest first.</span>
            </header>
            <HistoryList history={episode.history} error={episode.historyError} onRetry={() => void reload()} />
          </section>

          <DeletePanel episode={episode} go={go} />
        </aside>
      </div>
    </>
  );
}

/** Only the audio editor and the owner delete, and never a published episode. */
function DeletePanel({ episode, go }: { episode: Episode; go: Go }) {
  const me = useMe();
  const toast = useToast();
  const { reload } = useEpisodes();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const published = episode.stage === "published";
  const allowed = me.role !== "video_editor";
  if (!allowed) return null;

  async function confirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await deleteEpisode(episode.id);
      toast.push({ kind: "success", title: `Deleted “${episode.title}”`, detail: "Its posting slot is free again." });
      go({ screen: "schedule" });
      void reload();
    } catch (err) {
      setError(toApiError(err));
      setBusy(false);
    }
  }

  return (
    <section className="panel panel-danger">
      <header className="panel-head">
        <h2 className="display-md">Remove</h2>
        <span className="sec-sub">
          {published ? "Published episodes are the record; they stay." : "Deletes the audio, transcript and history, and frees the posting slot."}
        </span>
      </header>
      <div>
        <button type="button" className="btn btn-danger" disabled={published} onClick={() => setConfirming(true)}>
          Delete episode…
        </button>
      </div>
      {confirming && (
        <Dialog title="Delete episode" onClose={() => !busy && setConfirming(false)}>
          <form className="form" onSubmit={(e) => void confirm(e)}>
            <p className="form-hint">
              Delete <strong>{episode.title}</strong>? This removes its audio, transcript, history and posting slot. It
              can’t be undone.
            </p>
            {error && (
              <Banner kind="error">
                <ErrorDetail error={error} lead="Couldn’t delete the episode." />
              </Banner>
            )}
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => setConfirming(false)} disabled={busy}>
                Keep it
              </button>
              <button type="submit" className="btn btn-danger" disabled={busy}>
                {busy ? "Deleting…" : "Delete episode"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </section>
  );
}
