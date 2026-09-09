import { useMemo, useState } from "react";

import { Banner } from "../components/Banner";
import { BoardSkeleton } from "../components/BoardSkeleton";
import { EmptyState } from "../components/EmptyState";
import { ErrorDetail } from "../components/ErrorDetail";
import { ErrorPanel } from "../components/ErrorPanel";
import { RegisterEpisodeDialog } from "../components/RegisterEpisodeDialog";
import { canRegister, PIPELINE, ROLE_LABEL, STAGE_LABEL, waitingOn } from "../domain/workflow";
import { fmtDate, fmtDateLong, suggestedSlots, todayISO } from "../lib/dates";
import { type Episode, useEpisodes } from "../state/episodes";
import { useMe, useSession } from "../state/session";
import { Shell, Tabs, Who } from "./Shell";
import { type Go } from "./nav";

import "../styles/schedule.css";

const FREE_SLOTS_SHOWN = 2;

type Row =
  | { kind: "episode"; date: string; episode: Episode }
  | { kind: "free"; date: string }
  | { kind: "today"; date: string };

function tone(e: Episode): string {
  if (e.stage === "published") return "published";
  if (e.stage === "blocked") return "blocked";
  return e.schedule_status ?? "none";
}

/**
 * The sheet: dated rows in order, a "today" line between what is late and
 * what is next, and the next free dates on the two-week cadence interleaved
 * so a gap in the run is visible without opening a calendar.
 */
function buildRows(episodes: Episode[], today: string): Row[] {
  const dated = episodes
    .filter((e) => e.publish_on && e.stage !== "published")
    .sort((a, b) => a.publish_on!.localeCompare(b.publish_on!));
  const taken = new Set(episodes.map((e) => e.publish_on).filter((d): d is string => d !== null));
  const last = dated.length ? dated[dated.length - 1].publish_on! : null;
  const anchor = last && last > today ? last : today;
  const free = suggestedSlots(anchor, taken, { count: FREE_SLOTS_SHOWN, today });

  const rows: Row[] = [
    ...dated.map((e): Row => ({ kind: "episode", date: e.publish_on!, episode: e })),
    ...free.map((d): Row => ({ kind: "free", date: d })),
    { kind: "today", date: today },
  ];
  // Today's line sits after anything overdue and before anything due today or later.
  const rank = (r: Row) => (r.kind === "today" ? 0 : r.date < today ? -1 : 1);
  return rows.sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return rank(a) - rank(b);
  });
}

export function ScheduleScreen({ go }: { go: Go }) {
  const me = useMe();
  const { signOut } = useSession();
  const { episodes, error, stale, updatedAt, reload } = useEpisodes();
  const [registering, setRegistering] = useState<{ publishOn: string | null } | null>(null);
  const today = todayISO();

  const mayRegister = canRegister(me.role);
  const open = (publishOn: string | null = null) => setRegistering({ publishOn });

  const rows = useMemo(() => (episodes ? buildRows(episodes, today) : []), [episodes, today]);
  const undated = episodes?.filter((e) => !e.publish_on && e.stage !== "published") ?? [];
  const published = (episodes ?? [])
    .filter((e) => e.stage === "published")
    .sort((a, b) => (b.publish_on ?? "").localeCompare(a.publish_on ?? ""));
  const unknown = episodes?.filter((e) => e.stage === null) ?? [];

  const inFlight = (episodes ?? []).filter((e) => e.stage !== "published");
  const counts = {
    overdue: inFlight.filter((e) => e.schedule_status === "overdue").length,
    due_soon: inFlight.filter((e) => e.schedule_status === "due_soon").length,
    on_track: inFlight.filter((e) => e.schedule_status === "on_track").length,
    blocked: inFlight.filter((e) => e.stage === "blocked").length,
  };
  const next = rows.find((r): r is Extract<Row, { kind: "episode" }> => r.kind === "episode" && r.date >= today);

  let body;
  if (!episodes && error) {
    body = <ErrorPanel error={error} onRetry={() => void reload()} />;
  } else if (!episodes) {
    body = <BoardSkeleton />;
  } else if (episodes.length === 0) {
    body = <EmptyState onCreate={mayRegister ? () => open() : null} />;
  } else {
    body = (
      <>
        <ol className="run-sheet">
          {rows.map((row) => {
            if (row.kind === "today") {
              return (
                <li key="today" className="run-today" aria-label={`Today, ${fmtDateLong(today)}`}>
                  <span className="run-today-label">Today · {fmtDate(today)}</span>
                </li>
              );
            }
            if (row.kind === "free") {
              return (
                <li key={`free-${row.date}`} className="run run-free">
                  <span className="run-count" aria-hidden="true" />
                  <span className="run-date">{fmtDate(row.date)}</span>
                  <span className="run-main">
                    <span className="run-title">Free slot</span>
                    <span className="run-sub">Next date on the two-week cadence with nothing on it.</span>
                  </span>
                  {mayRegister && (
                    <button type="button" className="btn btn-sm" onClick={() => open(row.date)}>
                      Register for this date
                    </button>
                  )}
                </li>
              );
            }
            return (
              <li key={row.episode.id}>
                <EpisodeRow episode={row.episode} onOpen={() => go({ screen: "episode", id: row.episode.id })} />
              </li>
            );
          })}
        </ol>

        {undated.length > 0 && (
          <section className="run-group">
            <h2 className="run-group-head">No posting date</h2>
            <ol className="run-sheet">
              {undated.map((e) => (
                <li key={e.id}>
                  <EpisodeRow episode={e} onOpen={() => go({ screen: "episode", id: e.id })} />
                </li>
              ))}
            </ol>
          </section>
        )}

        {published.length > 0 && (
          <section className="run-group">
            <h2 className="run-group-head">Published</h2>
            <ol className="run-sheet run-sheet-done">
              {published.map((e) => (
                <li key={e.id}>
                  <EpisodeRow episode={e} onOpen={() => go({ screen: "episode", id: e.id })} />
                </li>
              ))}
            </ol>
          </section>
        )}
      </>
    );
  }

  return (
    <Shell go={go} center={<Tabs route={{ screen: "schedule" }} go={go} />} right={<Who me={me} onSignOut={() => signOut()} />}>
      <main className="page">
        <header className="sched-head">
          <div>
            <p className="eyebrow">
              The Sozzled Pod
              {episodes && ` · ${inFlight.length} in flight`}
              {next && ` · next out ${fmtDate(next.date)}`}
            </p>
            <h1 className="display-lg sched-title">Schedule</h1>
            <p className="sched-sub">
              Read top to bottom: what is late, what is next, where the gaps are. One episode per date.
            </p>
          </div>
          <div className="sched-actions">
            {episodes && episodes.length > 0 && (
              <span className="legend">
                <span className={counts.overdue ? "legend-hot" : undefined}>
                  <i className="key key-overdue" /> {counts.overdue} overdue
                </span>
                <span>
                  <i className="key key-due_soon" /> {counts.due_soon} due soon
                </span>
                <span>
                  <i className="key key-on_track" /> {counts.on_track} on track
                </span>
                {counts.blocked > 0 && (
                  <span>
                    <i className="key key-blocked" /> {counts.blocked} blocked
                  </span>
                )}
              </span>
            )}
            <button
              type="button"
              className="btn btn-accent"
              disabled={!mayRegister}
              title={mayRegister ? undefined : "Only the audio editor or owner registers episodes."}
              onClick={() => open()}
            >
              Register episode
            </button>
          </div>
        </header>

        {episodes && error && (
          <Banner kind="error">
            <ErrorDetail error={error} lead="Couldn't refresh the schedule." onRetry={() => void reload()} />
          </Banner>
        )}
        {episodes && !error && stale && updatedAt && (
          <Banner kind="warn">Showing data from {updatedAt.toLocaleTimeString()}.</Banner>
        )}
        {unknown.length > 0 && (
          <Banner kind="warn">
            The stage of {unknown.length === 1 ? "one episode" : `${unknown.length} episodes`} could
            not be loaded, so their progress is blank.{" "}
            <button type="button" className="link" onClick={() => void reload()}>
              Try again
            </button>
          </Banner>
        )}

        {body}
      </main>

      {registering && (
        <RegisterEpisodeDialog
          publishOn={registering.publishOn}
          onClose={() => setRegistering(null)}
          onCreated={(created) => {
            setRegistering(null);
            go({ screen: "episode", id: created.id });
          }}
        />
      )}
    </Shell>
  );
}

function EpisodeRow({ episode, onOpen }: { episode: Episode; onOpen: () => void }) {
  const stage = episode.stage;
  const stepIndex = stage ? PIPELINE.indexOf(stage) : -1;
  const done = stage === "published";
  const days = episode.days_remaining;
  const owner = stage ? waitingOn(stage) : null;

  const sub = done
    ? `Recorded ${fmtDate(episode.recorded_on)}`
    : stage === "blocked"
      ? "Blocked. Anyone can unblock it once the work can resume."
      : stage === null
        ? "Stage unknown"
        : owner
          ? `Waiting on the ${ROLE_LABEL[owner].toLowerCase()}`
          : `Recorded ${fmtDate(episode.recorded_on)}`;

  return (
    <button type="button" className={`run run-${tone(episode)}`} onClick={onOpen}>
      <span className="run-count">
        {done ? (
          <b className="run-count-done">✓</b>
        ) : episode.publish_on === null || days === null ? (
          <b className="run-count-none">—</b>
        ) : (
          <>
            <b>{Math.abs(days)}</b>
            <small>{days < 0 ? "overdue" : days === 0 ? "today" : "days"}</small>
          </>
        )}
      </span>
      <span className="run-date">{episode.publish_on ? fmtDate(episode.publish_on) : "No date"}</span>
      <span className="run-main">
        <span className="run-title">{episode.title}</span>
        <span className="run-sub">{sub}</span>
      </span>
      <span className="run-progress">
        <span
          className={`run-track${stage === "blocked" ? " run-track-blocked" : ""}`}
          role="img"
          aria-label={stage ? `${STAGE_LABEL[stage]}, step ${stepIndex + 1} of ${PIPELINE.length}` : "Stage unknown"}
        >
          {PIPELINE.map((s, i) => (
            <i key={s} className={i < stepIndex ? "seg-done" : i === stepIndex ? "seg-now" : "seg-next"} />
          ))}
        </span>
        <span className="run-stage">{stage ? STAGE_LABEL[stage] : "—"}</span>
      </span>
    </button>
  );
}
