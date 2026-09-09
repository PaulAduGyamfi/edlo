import { AudioPanel } from "../components/AudioPanel";
import { Banner } from "../components/Banner";
import { ErrorDetail } from "../components/ErrorDetail";
import { ErrorPanel } from "../components/ErrorPanel";
import { HistoryList } from "../components/HistoryList";
import { SlotCalendar } from "../components/SlotCalendar";
import { StagePanel } from "../components/StagePanel";
import { STAGE_LABEL } from "../domain/workflow";
import { fmtDate, fmtDateLong } from "../lib/dates";
import { type Episode, useEpisodes } from "../state/episodes";
import { useMe, useSession } from "../state/session";
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
    body = <EpisodeBody episode={episode} />;
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

function EpisodeBody({ episode }: { episode: Episode }) {
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
        </aside>
      </div>
    </>
  );
}
