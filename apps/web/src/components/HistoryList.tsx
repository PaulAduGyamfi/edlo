import { type ApiError } from "../api/client";
import { type Transition } from "../api/episodes";
import { actorName, ROLE_LABEL, STAGE_LABEL } from "../domain/workflow";
import { fmtStamp } from "../lib/dates";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

export function HistoryList({
  history,
  error,
  onRetry,
}: {
  history: Transition[] | null;
  error: ApiError | null;
  onRetry: () => void;
}) {
  if (!history) {
    return error ? (
      <Banner kind="error">
        <ErrorDetail error={error} lead="Couldn't load the history." onRetry={onRetry} />
      </Banner>
    ) : (
      <p className="panel-empty">Loading…</p>
    );
  }
  if (history.length === 0) {
    return <p className="panel-empty">No moves yet. Registered is where every episode starts.</p>;
  }
  const newestFirst = history.slice().reverse();
  return (
    <ol className="hist">
      {newestFirst.map((t, i) => (
        <li className="hist-item" key={`${t.at}-${i}`}>
          <span className={`hist-dot hist-${t.to === "blocked" ? "blocked" : "move"}`} aria-hidden="true" />
          <div className="hist-body">
            <span className="hist-move">
              <span className="hist-from">{STAGE_LABEL[t.from] ?? t.from}</span>
              <span className="hist-arrow" aria-hidden="true">
                →
              </span>
              <span className="hist-to">{STAGE_LABEL[t.to] ?? t.to}</span>
            </span>
            <span className="hist-meta">
              {actorName(t.actor)} · {ROLE_LABEL[t.role] ?? t.role} · {fmtStamp(t.at)}
            </span>
            {t.reason && <span className="hist-reason">“{t.reason}”</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}
