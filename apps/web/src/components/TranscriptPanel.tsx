import { type KeyboardEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type ApiError, makeError, toApiError } from "../api/client";
import { getDownloadUrl, getTranscript, storageUrl, type Transcript } from "../api/episodes";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

type State =
  | { status: "loading" }
  | { status: "absent" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; transcript: Transcript };

const RATES = [1, 1.25, 1.5, 2];
const SKIP_MS = 5000;

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
  return <TranscriptView episodeId={episodeId} transcript={state.transcript} />;
}

/**
 * One clock, three views of it: the audio element, the playhead on the
 * timeline, and the highlighted row. Playback drives all three; dragging the
 * timeline or clicking a row moves the clock; the list follows the clock
 * until the reader scrolls away on their own.
 */
function TranscriptView({ episodeId, transcript }: { episodeId: string; transcript: Transcript }) {
  const { segments, duration_ms } = transcript;
  const toast = useToast();
  const listRef = useRef<HTMLDivElement>(null);
  const scrubRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const headRef = useRef<HTMLElement>(null);
  const fillRef = useRef<HTMLElement>(null);
  const clockRef = useRef<HTMLSpanElement>(null);
  const lastProgrammaticScroll = useRef(0);
  const refreshedUrl = useRef(false);

  const [current, setCurrent] = useState(0);
  const [timeMs, setTimeMs] = useState(0); // the clock as of the last seek or pause; the playhead paints per frame
  const [playing, setPlaying] = useState(false);
  const [follow, setFollow] = useState(true);
  const [rate, setRate] = useState(1);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [audioError, setAudioError] = useState<ApiError | null>(null);
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

  /** Index of the segment that contains `ms` (the last one starting at or before it). */
  const segmentAt = useCallback(
    (ms: number) => {
      let lo = 0;
      let hi = segments.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (segments[mid].start_ms <= ms) lo = mid;
        else hi = mid - 1;
      }
      return lo;
    },
    [segments],
  );

  const scrollToIndex = useCallback((i: number, behavior: ScrollBehavior = "smooth") => {
    const list = listRef.current;
    const row = list?.children[i] as HTMLElement | undefined;
    if (list && row) {
      lastProgrammaticScroll.current = Date.now();
      list.scrollTo({ top: row.offsetTop, behavior });
    }
  }, []);

  /** Move the playhead, progress fill and clock without a React render. */
  const paint = useCallback(
    (ms: number) => {
      const p = `${Math.min(100, Math.max(0, (ms / duration_ms) * 100))}%`;
      const head = headRef.current;
      if (head) {
        head.style.left = p;
        head.classList.toggle("tx-head-flip", ms / duration_ms > 0.8);
        if (head.firstElementChild) head.firstElementChild.textContent = fmtTime(ms);
      }
      if (fillRef.current) fillRef.current.style.width = p;
      if (clockRef.current) clockRef.current.textContent = fmtTime(ms);
    },
    [duration_ms],
  );

  /** Set the clock: paint, select the segment, and move the audio if it is loaded. */
  const seekTo = useCallback(
    (ms: number, scroll = true) => {
      const clamped = Math.min(duration_ms, Math.max(0, ms));
      paint(clamped);
      setTimeMs(clamped);
      const i = segmentAt(clamped);
      setCurrent(i);
      if (scroll) scrollToIndex(i);
      const a = audioRef.current;
      if (a && a.src) a.currentTime = clamped / 1000;
    },
    [duration_ms, paint, segmentAt, scrollToIndex],
  );

  // While playing, follow the audio clock frame by frame.
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = -1;
    const tick = () => {
      const a = audioRef.current;
      if (!a) return;
      const ms = a.currentTime * 1000;
      paint(ms);
      const i = segmentAt(ms);
      if (i !== last) {
        last = i;
        setCurrent(i);
        if (follow) scrollToIndex(i);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, follow, paint, segmentAt, scrollToIndex]);

  /** The rough mix is fetched on first play, not on page load. */
  async function ensureAudio(): Promise<HTMLAudioElement | null> {
    const a = audioRef.current;
    if (!a) return null;
    if (a.src) return a;
    setLoadingAudio(true);
    setAudioError(null);
    try {
      const { url } = await getDownloadUrl(episodeId, "rough", { stamp: false });
      a.src = storageUrl(url);
      a.playbackRate = rate;
      a.currentTime = timeMs / 1000;
      return a;
    } catch (e) {
      setAudioError(toApiError(e));
      return null;
    } finally {
      setLoadingAudio(false);
    }
  }

  async function togglePlay() {
    const a = await ensureAudio();
    if (!a) return;
    if (!a.paused) {
      a.pause();
      return;
    }
    try {
      await a.play();
    } catch {
      setAudioError(makeError(0, "The browser refused to start playback.", null));
    }
  }

  async function playFrom(ms: number) {
    seekTo(ms);
    setFollow(true);
    const a = await ensureAudio();
    if (!a) return;
    a.currentTime = ms / 1000;
    try {
      await a.play();
    } catch {
      setAudioError(makeError(0, "The browser refused to start playback.", null));
    }
  }

  /** A presigned URL expires; fetch a fresh one once and resume where we were. */
  async function onAudioError() {
    const a = audioRef.current;
    if (!a || refreshedUrl.current) {
      setAudioError(makeError(0, "The audio stopped loading.", null));
      return;
    }
    refreshedUrl.current = true;
    const at = a.currentTime;
    const wasPlaying = !a.paused;
    a.removeAttribute("src");
    const fresh = await ensureAudio();
    if (!fresh) return;
    fresh.currentTime = at;
    if (wasPlaying) void fresh.play();
  }

  function cycleRate() {
    const next = RATES[(RATES.indexOf(rate) + 1) % RATES.length];
    setRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  }

  // While the selected row is on screen it stays selected; once it scrolls
  // away, the first row at or below the top edge takes over. A scroll the
  // reader made during playback switches follow off.
  function onScroll() {
    const list = listRef.current;
    if (!list) return;
    const programmatic = Date.now() - lastProgrammaticScroll.current < 700;
    if (playing) {
      if (!programmatic) setFollow(false);
      return;
    }
    const rows = list.children;
    const top = list.scrollTop;
    const sel = rows[current] as HTMLElement | undefined;
    if (sel && sel.offsetTop >= top && sel.offsetTop + sel.offsetHeight <= top + list.clientHeight) return;
    let lo = 0;
    let hi = rows.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      const r = rows[mid] as HTMLElement;
      if (r.offsetTop + r.offsetHeight > top + 1) hi = mid;
      else lo = mid + 1;
    }
    setCurrent(lo);
  }

  function barTime(clientX: number): number {
    const bar = scrubRef.current;
    if (!bar) return 0;
    const rect = bar.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) * duration_ms;
  }

  function jump(pos: number) {
    if (!hits.length) return;
    const next = ((pos % hits.length) + hits.length) % hits.length;
    setHit({ q, pos: next });
    seekTo(segments[hits[next]].start_ms);
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.target instanceof HTMLInputElement) return;
    const a = audioRef.current;
    const now = a && a.src ? a.currentTime * 1000 : timeMs;
    if (e.key === " ") {
      e.preventDefault();
      void togglePlay();
    } else if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      seekTo(segments[Math.min(segments.length - 1, current + 1)].start_ms);
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      seekTo(segments[Math.max(0, current - 1)].start_ms);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      seekTo(now + SKIP_MS);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      seekTo(now - SKIP_MS);
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

  return (
    <div className="tx" onKeyDown={onKey}>
      <audio
        ref={audioRef}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false);
          if (audioRef.current) setTimeMs(audioRef.current.currentTime * 1000);
        }}
        onEnded={() => setPlaying(false)}
        onError={() => void onAudioError()}
      />

      <div className="tx-player">
        <button
          type="button"
          className="tx-play"
          onClick={() => void togglePlay()}
          disabled={loadingAudio}
          aria-label={playing ? "Pause" : "Play the rough mix"}
          aria-pressed={playing}
        >
          {loadingAudio ? (
            "…"
          ) : playing ? (
            <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
              <rect x="1.5" y="1" width="3.5" height="10" rx="1" fill="currentColor" />
              <rect x="7" y="1" width="3.5" height="10" rx="1" fill="currentColor" />
            </svg>
          ) : (
            <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
              <path d="M2.5 1.2 11 6 2.5 10.8Z" fill="currentColor" />
            </svg>
          )}
        </button>
        <span className="tx-clock">
          <span ref={clockRef}>{fmtTime(timeMs)}</span>
          <span className="tx-clock-total"> / {fmtTime(duration_ms)}</span>
        </span>
        <button type="button" className="btn btn-sm" onClick={cycleRate} aria-label="Playback speed">
          {rate}×
        </button>
        {playing && !follow && (
          <button
            type="button"
            className="btn btn-sm btn-accent"
            onClick={() => {
              setFollow(true);
              scrollToIndex(current);
            }}
          >
            Follow playback
          </button>
        )}
        <div className="tx-search">
          <input
            type="search"
            placeholder="Search the transcript"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              const first = findHits(e.target.value.trim().toLowerCase())[0];
              if (first !== undefined) seekTo(segments[first].start_ms);
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

      {audioError && (
        <Banner kind="error">
          <ErrorDetail error={audioError} lead="Couldn't play the rough mix." onRetry={() => void togglePlay()} />
        </Banner>
      )}

      <div
        ref={scrubRef}
        className="tx-scrub"
        role="slider"
        aria-label="Timeline"
        aria-valuemin={0}
        aria-valuemax={duration_ms}
        aria-valuenow={timeMs}
        aria-valuetext={fmtTime(timeMs)}
        onPointerDown={(e) => {
          seekTo(barTime(e.clientX), false);
          try {
            e.currentTarget.setPointerCapture(e.pointerId); // keep dragging past the edge
          } catch {
            // synthetic or already-released pointer: the click still seeked
          }
        }}
        onPointerMove={(e) => {
          if (e.buttons & 1) seekTo(barTime(e.clientX), false);
        }}
        onPointerUp={() => scrollToIndex(current)}
      >
        <i ref={fillRef} className="tx-fill" style={{ width: pct(timeMs) }} />
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
        <i ref={headRef} className={`tx-head${timeMs / duration_ms > 0.8 ? " tx-head-flip" : ""}`} style={{ left: pct(timeMs) }}>
          <span>{fmtTime(timeMs)}</span>
        </i>
      </div>

      <div ref={listRef} className="tx-list" tabIndex={0} onScroll={onScroll} aria-label="Transcript">
        {segments.map((s, i) => (
          <div
            key={s.index}
            className={`tx-row${i === current ? " tx-row-now" : ""}`}
            onClick={() => void playFrom(s.start_ms)}
            title="Play from here"
          >
            <button
              type="button"
              className="tx-time"
              onClick={(e) => {
                e.stopPropagation();
                copyTime(s.start_ms);
              }}
              title="Copy timecode"
            >
              {fmtTime(s.start_ms)}
            </button>
            <p>
              <Highlight text={s.text} q={q} />
            </p>
          </div>
        ))}
      </div>

      <p className="tx-foot">
        <span>
          Click a line to play from it · drag the timeline to seek · Space plays, ← → skip 5s, ↑ ↓ step a line · Enter jumps
          between matches · click a timecode to copy it.
        </span>
        <span>
          {transcript.engine} · {transcript.model_version} · {transcript.language}
        </span>
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
