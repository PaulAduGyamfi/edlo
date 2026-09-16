const pad = (n: number) => String(n).padStart(2, "0");

/** 0:07, 12:34, 1:02:03 */
export function fmtTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}

/** 0:07.250 — what an editor types into a timeline. */
export const fmtTimeMs = (ms: number) => `${fmtTime(ms)}.${String(ms % 1000).padStart(3, "0")}`;

export const toSeconds = (ms: number) => (ms / 1000).toFixed(1);
export const fromSeconds = (s: string) => Math.round(Number.parseFloat(s) * 1000);

/** 42s, 21m 03s, 1h 12m — how long something has been going on. */
export function fmtDur(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}
