import { type KeyboardEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { getTranscript, type Transcript } from "../api/episodes";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

type State =
  | { status: "loading" }
  | { status: "absent" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; transcript: Transcript };

const pad = (n: number) => String(n).padStart(2, "0");

function fmtTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}

/** Tick spacing that gives the timeline six to ten labels. */
function tickStep(durationMs: number): number {
  for (const step of [15e3, 30e3, 60e3, 120e3, 300e3, 600e3, 900e3, 1800e3]) {
    if (durationMs / step <= 10) return step;
  }
  return 3600e3;
}

export function TranscriptPanel({ episodeId }: { episodeId: string }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getTranscript(episodeId).then(
      (transcript) => {
        if (!cancelled) setState({ status: "ready", transcript });
      },
      (e: unknown) => {
        if (cancelled) return;
        const err = toApiError(e);
        setState(err.status === 404 ? { status: "absent" } : { status: "error", error: err });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [episodeId, attempt]);

  const retry = () => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  };

  if (state.status === "loading") {
    return (
      <p className="panel-empty" aria-busy="true">
        Loading transcript…
      </p>
    );
  }
  if (state.status === "absent") {
    return <p className="panel-empty">No transcript yet. One is produced when the rough mix upload completes.</p>;
  }
  if (state.status === "error") {
    return (
      <Banner kind="error">
        <ErrorDetail error={state.error} lead="Couldn't load the transcript." onRetry={retry} />
      </Banner>
    );
  }
  return <TranscriptView transcript={state.transcript} />;
}

/**
 * The timeline and the list are one scroll position seen two ways: scrolling
 * the list moves the playhead, dragging the timeline scrolls the list.
 */
function TranscriptView({ transcript }: { transcript: Transcript }) {
  const { segments, duration_ms } = transcript;
  const toast = useToast();
  const listRef = useRef<HTMLDivElement>(null);
  const scrubRef = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(0);
  const [query, setQuery] = useState("");
  const [hit, setHit] = useState({ q: "", pos: 0 });

  const q = query.trim().toLowerCase();
  const findHits = useCallback(
    (needle: string) =>
      needle ? segments.flatMap((s, i) => (s.text.toLowerCase().includes(needle) ? [i] : [])) : [],
    [segments],
  );
  const hits = useMemo(() => findHits(q), [findHits, q]);
  const hitPos = hit.q === q ? hit.pos : 0; // a new query starts at its first match

  const scrollToIndex = useCallback((i: number, behavior: ScrollBehavior = "smooth") => {
    setCurrent(i);
    const list = listRef.current;
    const row = list?.children[i] as HTMLElement | undefined;
    if (list && row) list.scrollTo({ top: row.offsetTop, behavior });
  }, []);

  // While the selected row is on screen it stays selected; once it scrolls
  // away, the first row at or below the top edge takes over.
  function onScroll() {
    const list = listRef.current;
    if (!list) return;
    const rows = list.children;
    const top = list.scrollTop;
    const sel = rows[current] as HTMLElement | undefined;
    if (sel && sel.offsetTop >= top && sel.offsetTop + sel.offsetHeight <= top + list.clientHeight) return;
    let lo = 0;
    let hi = rows.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      const r = rows[mid] as HTMLElement;
      if (r.offsetTop + r.offsetHeight > list.scrollTop + 1) hi = mid;
      else lo = mid + 1;
    }
    setCurrent(lo);
  }

  function seek(clientX: number) {
    const bar = scrubRef.current;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    const t = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) * duration_ms;
    let i = segments.findIndex((s) => s.end_ms > t);
    if (i < 0) i = segments.length - 1;
    scrollToIndex(i, "auto");
  }

  function jump(pos: number) {
    if (!hits.length) return;
    const next = ((pos % hits.length) + hits.length) % hits.length;
    setHit({ q, pos: next });
    scrollToIndex(hits[next]);
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      scrollToIndex(Math.min(segments.length - 1, current + 1));
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      scrollToIndex(Math.max(0, current - 1));
    }
  }

  function copyTime(ms: number) {
    const stamp = fmtTime(ms);
    void navigator.clipboard?.writeText(stamp).then(() => toast.push({ kind: "info", title: `Copied ${stamp}` }));
  }

  const step = tickStep(duration_ms);
  const ticks: number[] = [];
  for (let t = step; t < duration_ms; t += step) ticks.push(t);
  const pct = (ms: number) => `${(ms / duration_ms) * 100}%`;
  const now = segments[current];

  return (
    <div className="tx">
      <div className="tx-tools">
        <div className="tx-chips">
          <span className="tx-chip">{fmtTime(duration_ms)}</span>
          <span className="tx-chip">{segments.length} segments</span>
          <span className="tx-chip">
            {transcript.engine} · {transcript.model_version}
          </span>
        </div>
        <div className="tx-search">
          <input
            type="search"
            placeholder="Search the transcript"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              const first = findHits(e.target.value.trim().toLowerCase())[0];
              if (first !== undefined) scrollToIndex(first);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") jump(e.shiftKey ? hitPos - 1 : hitPos + 1);
            }}
            aria-label="Search the transcript"
          />
          <span className="tx-search-count" aria-live="polite">
            {q ? (hits.length ? `${hitPos + 1} of ${hits.length}` : "no matches") : ""}
          </span>
          <button type="button" className="btn btn-sm" disabled={!hits.length} onClick={() => jump(hitPos - 1)} aria-label="Previous match">
            ‹
          </button>
          <button type="button" className="btn btn-sm" disabled={!hits.length} onClick={() => jump(hitPos + 1)} aria-label="Next match">
            ›
          </button>
        </div>
      </div>

      <div
        ref={scrubRef}
        className="tx-scrub"
        role="slider"
        aria-label="Timeline"
        aria-valuemin={0}
        aria-valuemax={duration_ms}
        aria-valuenow={now?.start_ms ?? 0}
        aria-valuetext={fmtTime(now?.start_ms ?? 0)}
        onPointerDown={(e) => {
          seek(e.clientX);
          try {
            e.currentTarget.setPointerCapture(e.pointerId); // keep dragging past the edge
          } catch {
            // synthetic or already-released pointer: the click still seeked
          }
        }}
        onPointerMove={(e) => {
          if (e.buttons & 1) seek(e.clientX);
        }}
      >
        {ticks.map((t) => (
          <i key={t} className="tx-tick" style={{ left: pct(t) }}>
            <span>{fmtTime(t)}</span>
          </i>
        ))}
        {segments.map((s, i) => (
          <i
            key={s.index}
            className={`tx-blip${hits.includes(i) ? " tx-blip-hit" : ""}`}
            style={{ left: pct(s.start_ms), width: `max(2px, ${pct(s.end_ms - s.start_ms)})` }}
          />
        ))}
        {now && (
          <i className={`tx-head${now.start_ms / duration_ms > 0.8 ? " tx-head-flip" : ""}`} style={{ left: pct(now.start_ms) }}>
            <span>{fmtTime(now.start_ms)}</span>
          </i>
        )}
      </div>

      <div ref={listRef} className="tx-list" tabIndex={0} onScroll={onScroll} onKeyDown={onKey} aria-label="Transcript">
        {segments.map((s, i) => (
          <div key={s.index} className={`tx-row${i === current ? " tx-row-now" : ""}`}>
            <button type="button" className="tx-time" onClick={() => copyTime(s.start_ms)} title="Copy timecode">
              {fmtTime(s.start_ms)}
            </button>
            <p>
              <Highlight text={s.text} q={q} />
            </p>
          </div>
        ))}
      </div>

      <p className="tx-foot">
        <span>Drag the timeline or scroll the list · ↑ ↓ step a segment · Enter jumps between matches · click a timecode to copy it.</span>
        <span>{transcript.language}</span>
      </p>
    </div>
  );
}

function Highlight({ text, q }: { text: string; q: string }) {
  if (!q) return <>{text}</>;
  const parts: ReactNode[] = [];
  const lower = text.toLowerCase();
  let i = 0;
  let at = lower.indexOf(q);
  while (at >= 0) {
    parts.push(text.slice(i, at));
    parts.push(<mark key={at}>{text.slice(at, at + q.length)}</mark>);
    i = at + q.length;
    at = lower.indexOf(q, i);
  }
  parts.push(text.slice(i));
  return <>{parts}</>;
}
