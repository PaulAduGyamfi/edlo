// Dates are YYYY-MM-DD strings end to end. Parsing them as local calendar
// days (never through Date.parse) keeps a Thursday a Thursday in every zone.

export function parseISODate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function toISODate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const todayISO = () => toISODate(new Date());

export function addDays(iso: string, n: number): string {
  const d = parseISODate(iso);
  d.setDate(d.getDate() + n);
  return toISODate(d);
}

const SHORT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
});
const LONG = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const MONTH = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });
const STAMP = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export const fmtDate = (iso: string) => SHORT.format(parseISODate(iso));
export const fmtDateLong = (iso: string) => LONG.format(parseISODate(iso));
export const fmtMonth = (d: Date) => MONTH.format(d);

/** Server timestamps are UTC; SQLite drops the offset, so add it back. */
export function parseStamp(s: string): Date {
  return new Date(/(?:Z|[+-]\d\d:?\d\d)$/.test(s) ? s : `${s}Z`);
}

export const fmtStamp = (s: string) => STAMP.format(parseStamp(s));

/**
 * The server's rule for a fresh episode: every 14 days after the recording,
 * skipping dates that already hold an episode. We also skip the past, which
 * the server would reject on assignment anyway.
 */
export function suggestedSlots(
  recordedOn: string,
  taken: ReadonlySet<string>,
  { count = 3, cadenceDays = 14, today = todayISO() } = {},
): string[] {
  const out: string[] = [];
  let candidate = addDays(recordedOn, cadenceDays);
  for (let guard = 0; out.length < count && guard < 200; guard++) {
    if (candidate >= today && !taken.has(candidate)) out.push(candidate);
    candidate = addDays(candidate, cadenceDays);
  }
  return out;
}

export type CountdownInput = {
  publish_on: string | null;
  days_remaining: number | null;
  stage?: string | null;
};

export function countdownText(ep: CountdownInput): string {
  if (ep.stage === "published") return "Published";
  if (ep.publish_on === null || ep.days_remaining === null) return "No posting date";
  const d = ep.days_remaining;
  if (d === 0) return "Publishes today";
  if (d < 0) return `${-d} day${d === -1 ? "" : "s"} overdue`;
  return `${d} day${d === 1 ? "" : "s"} to publish`;
}
