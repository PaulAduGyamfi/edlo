import { useMemo, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { setSlot } from "../api/episodes";
import {
  addDays,
  fmtDate,
  fmtDateLong,
  fmtMonth,
  parseISODate,
  suggestedSlots,
  toISODate,
  todayISO,
} from "../lib/dates";
import { type Episode, useEpisodes } from "../state/episodes";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Cell = {
  iso: string;
  day: number;
  inMonth: boolean;
  past: boolean;
  today: boolean;
  mine: boolean;
  suggested: boolean;
  takenBy: string | null;
};

function monthOf(iso: string): Date {
  const d = parseISODate(iso);
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function SlotCalendar({ episode }: { episode: Episode }) {
  const { episodes, patch } = useEpisodes();
  const toast = useToast();
  const today = todayISO();
  const [month, setMonth] = useState<Date>(() => monthOf(episode.publish_on ?? today));
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Dates other episodes already hold. One episode per date is the rule.
  const taken = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of episodes ?? []) {
      if (e.id !== episode.id && e.publish_on) map.set(e.publish_on, e.title);
    }
    return map;
  }, [episodes, episode.id]);

  const suggestions = useMemo(() => {
    const blocked = new Set(taken.keys());
    if (episode.publish_on) blocked.add(episode.publish_on);
    return suggestedSlots(episode.recorded_on, blocked, { today });
  }, [episode.recorded_on, episode.publish_on, taken, today]);

  const cells = useMemo<Cell[]>(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7; // Monday-first
    const start = addDays(toISODate(first), -offset);
    const suggested = new Set(suggestions);
    return Array.from({ length: 42 }, (_, i) => {
      const iso = addDays(start, i);
      const d = parseISODate(iso);
      return {
        iso,
        day: d.getDate(),
        inMonth: d.getMonth() === month.getMonth(),
        past: iso < today,
        today: iso === today,
        mine: iso === episode.publish_on,
        suggested: suggested.has(iso),
        takenBy: taken.get(iso) ?? null,
      };
    });
  }, [month, suggestions, taken, today, episode.publish_on]);

  function shift(delta: number) {
    setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));
  }

  function pick(iso: string) {
    setError(null);
    setPending(iso);
    setMonth(monthOf(iso));
  }

  async function confirm() {
    if (!pending || busy) return;
    setBusy(true);
    setError(null);
    try {
      const summary = await setSlot(episode.id, pending);
      patch(summary);
      toast.push({ kind: "success", title: `Posting slot set to ${fmtDate(pending)}` });
      setPending(null);
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setBusy(false);
    }
  }

  const published = episode.stage === "published";

  return (
    <div className="cal">
      <div className="cal-nav">
        <button type="button" className="btn btn-sm" onClick={() => shift(-1)} aria-label="Previous month">
          ‹
        </button>
        <span className="cal-month">{fmtMonth(month)}</span>
        <button type="button" className="btn btn-sm" onClick={() => shift(1)} aria-label="Next month">
          ›
        </button>
      </div>

      <div className="cal-grid" role="grid" aria-label="Posting slot calendar">
        {WEEKDAYS.map((w) => (
          <span key={w} className="cal-weekday" role="columnheader">
            {w}
          </span>
        ))}
        {cells.map((c) => {
          const disabled = published || c.past || c.takenBy !== null || c.mine;
          const classes = [
            "cal-cell",
            c.inMonth ? "" : "cal-out",
            c.past ? "cal-past" : "",
            c.today ? "cal-today" : "",
            c.mine ? "cal-mine" : "",
            c.takenBy ? "cal-taken" : "",
            c.suggested ? "cal-suggest" : "",
            pending === c.iso ? "cal-pending" : "",
          ]
            .filter(Boolean)
            .join(" ");
          const title = c.mine
            ? "This episode's posting date"
            : c.takenBy
              ? `Taken: ${c.takenBy}`
              : c.suggested
                ? "Next free slot on the two-week cadence"
                : c.past
                  ? "In the past"
                  : fmtDateLong(c.iso);
          return (
            <button
              key={c.iso}
              type="button"
              role="gridcell"
              className={classes}
              disabled={disabled}
              title={title}
              aria-label={`${fmtDateLong(c.iso)}${c.takenBy ? `, taken by ${c.takenBy}` : ""}`}
              onClick={() => pick(c.iso)}
            >
              <span className="cal-day">{c.day}</span>
              {c.takenBy && <span className="cal-tag">{c.takenBy}</span>}
              {c.mine && <span className="cal-tag cal-tag-mine">This episode</span>}
            </button>
          );
        })}
      </div>

      <div className="cal-legend">
        <span>
          <i className="cal-key cal-key-mine" /> current
        </span>
        <span>
          <i className="cal-key cal-key-suggest" /> next free
        </span>
        <span>
          <i className="cal-key cal-key-taken" /> taken
        </span>
      </div>

      {!published && suggestions.length > 0 && (
        <div className="cal-suggestions">
          <span className="cal-suggestions-label">Next free slots</span>
          {suggestions.map((iso, i) => (
            <button
              key={iso}
              type="button"
              className={`chip chip-btn${i === 0 ? " chip-accent" : ""}`}
              onClick={() => pick(iso)}
            >
              {fmtDate(iso)}
            </button>
          ))}
        </div>
      )}

      {pending && (
        <div className="confirm">
          <span>
            Set the posting slot to <strong>{fmtDateLong(pending)}</strong>?
          </span>
          <button type="button" className="btn btn-sm" onClick={() => setPending(null)} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="btn btn-sm btn-accent" onClick={() => void confirm()} disabled={busy}>
            {busy ? "Setting…" : "Set slot"}
          </button>
        </div>
      )}

      {error && (
        <Banner kind="error">
          <ErrorDetail error={error} lead="Couldn't set that slot." />
        </Banner>
      )}
    </div>
  );
}
