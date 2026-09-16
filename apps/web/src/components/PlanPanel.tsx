import { type FormEvent, useEffect, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import {
  type ColdOpenView,
  type CutItemView,
  type Decision,
  decideCut,
  generatePlan,
  getPlan,
  getPlanExport,
  type JobView,
  pickColdOpen,
  type PlanView,
  type StepView,
  tickStep,
} from "../api/episodes";
import { useJob } from "../hooks/useJob";
import { fmtTimeMs, fromSeconds, toSeconds } from "../lib/time";
import { type Episode, useEpisodes } from "../state/episodes";
import { useMe } from "../state/session";
import { errorToast, useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

type State =
  | { status: "loading" }
  | { status: "none" }
  | { status: "pending"; job: JobView }
  | { status: "error"; error: ApiError }
  | { status: "ready"; plan: PlanView };

const RULE_LABEL: Record<string, string> = {
  quote_not_in_transcript: "quote not in transcript",
  quote_not_at_timecode: "quote not at its timecode",
  timecode_out_of_range: "timecode outside the episode",
  timecode_inverted: "timecode inverted",
  quote_too_short: "quote too short",
  span_too_long: "span too long",
  over_cap: "over the cap",
};

/**
 * The model proposes, code validates, a person decides. Human flags arrive
 * here untouched; every model item survived four grounding rules first.
 */
export function PlanPanel({ episode }: { episode: Episode }) {
  const me = useMe();
  const toast = useToast();
  const { reload } = useEpisodes();
  const editor = me.role !== "audio_editor";
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPlan(episode.id).then(
      (data) => {
        if (cancelled) return;
        if ("job" in data) setState({ status: "pending", job: data.job });
        else setState({ status: "ready", plan: data });
      },
      (e: unknown) => {
        if (cancelled) return;
        const err = toApiError(e);
        setState(err.status === 404 ? { status: "none" } : { status: "error", error: err });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [episode.id, attempt]);

  const refresh = () => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  };

  const polled = useJob(state.status === "pending" ? state.job.id : null, (job) => {
    if (job.status === "succeeded") {
      refresh();
      void reload(); // the worker moved the episode to plan ready
    }
  });

  async function generate() {
    setBusy(true);
    try {
      await generatePlan(episode.id);
      refresh();
    } catch (e) {
      toast.push(errorToast(e, "Couldn't start the plan"));
    } finally {
      setBusy(false);
    }
  }

  const patchPlan = (fn: (p: PlanView) => PlanView) =>
    setState((s) => (s.status === "ready" ? { status: "ready", plan: fn(s.plan) } : s));

  if (state.status === "loading") {
    return (
      <p className="panel-empty" aria-busy="true">
        Loading plan…
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <Banner kind="error">
        <ErrorDetail error={state.error} lead="Couldn't load the plan." onRetry={refresh} />
      </Banner>
    );
  }
  if (state.status === "none") {
    return (
      <div className="plan-empty">
        <p className="panel-empty">
          No plan yet. It is built from the transcript: flagged moments first, then grounded cut and cold-open
          proposals, then the fixed checklist.
        </p>
        {editor && (
          <button type="button" className="btn btn-accent" disabled={busy} onClick={() => void generate()}>
            {busy ? "Starting…" : "Build the plan"}
          </button>
        )}
      </div>
    );
  }
  if (state.status === "pending") {
    const job = polled && polled.id === state.job.id ? polled : state.job;
    if (job.status === "dead") {
      return (
        <Banner kind="error">
          <strong>The plan could not be built.</strong> {job.user_message ?? "Something went wrong in the background."}{" "}
          {editor && (
            <button type="button" className="btn btn-sm" onClick={() => void generate()}>
              Try again
            </button>
          )}
        </Banner>
      );
    }
    return (
      <div className="tx-pending" role="status" aria-busy="true">
        <span className="tx-pending-dot" aria-hidden="true" />
        <div>
          <strong>{job.status === "running" ? "Building the plan…" : "Waiting for a worker…"}</strong>
          <span className="tx-pending-sub">One model call per five-minute window. You can close this tab.</span>
        </div>
      </div>
    );
  }

  const { plan } = state;
  const dropped = Object.values(plan.rejections).reduce((a, b) => a + b, 0);
  const accepted = plan.items.filter((i) => i.decision === "accepted").length;

  async function copyExport() {
    try {
      const text = await getPlanExport(episode.id);
      await navigator.clipboard.writeText(text);
      toast.push({ kind: "info", title: "Cut list copied", detail: `${accepted} accepted cut${accepted === 1 ? "" : "s"} as timecodes.` });
    } catch (e) {
      toast.push(errorToast(e, "Couldn't copy the cut list"));
    }
  }

  return (
    <div className="plan">
      {plan.status === "ai_disabled" ? (
        <Banner kind="info">
          AI suggestions are turned off. The workflow is running normally: moments flagged in the transcript are the
          cut list.
        </Banner>
      ) : (
        <p className="plan-meta">
          <span className="tx-chip">{plan.model}</span>
          <span className="tx-chip">{plan.prompt_version}</span>
          <span>
            {plan.windows} window{plan.windows === 1 ? "" : "s"} · {plan.proposed} proposed ·{" "}
            <strong>{dropped} dropped by grounding</strong>
            {dropped > 0 && (
              <>
                {" "}
                (
                {Object.entries(plan.rejections)
                  .map(([rule, n]) => `${RULE_LABEL[rule] ?? rule} ×${n}`)
                  .join(", ")}
                )
              </>
            )}
          </span>
        </p>
      )}

      <div className="plan-section">
        <h3 className="plan-sub">
          Cuts <span>{accepted} of {plan.items.length} accepted</span>
        </h3>
        {plan.items.length === 0 ? (
          <p className="panel-empty">Nothing to cut. Flag a moment in the transcript to add one.</p>
        ) : (
          <ul className="cuts">
            {plan.items.map((item) => (
              <CutRow
                key={item.id}
                episodeId={episode.id}
                item={item}
                editor={editor}
                onChange={(updated) =>
                  patchPlan((p) => ({ ...p, items: p.items.map((i) => (i.id === updated.id ? updated : i)) }))
                }
              />
            ))}
          </ul>
        )}
      </div>

      <div className="plan-section">
        <h3 className="plan-sub">Cold open</h3>
        {plan.cold_opens.length === 0 ? (
          <p className="panel-empty">
            {plan.status === "ready"
              ? "No cold open proposed. The model returned nothing strong enough, which is allowed."
              : "Cold opens need AI suggestions."}
          </p>
        ) : (
          <ul className="colds">
            {plan.cold_opens.map((c) => (
              <ColdCard
                key={c.id}
                episodeId={episode.id}
                cold={c}
                editor={editor}
                onChange={(updated) =>
                  patchPlan((p) => ({
                    ...p,
                    cold_opens: p.cold_opens.map((x) =>
                      x.id === updated.id ? updated : updated.picked ? { ...x, picked: false } : x,
                    ),
                  }))
                }
              />
            ))}
          </ul>
        )}
      </div>

      <div className="plan-section">
        <h3 className="plan-sub">
          Checklist <span>the same every episode, on purpose</span>
        </h3>
        <ul className="steps">
          {plan.steps.map((s) => (
            <StepRow
              key={s.id}
              episodeId={episode.id}
              step={s}
              editor={editor}
              onChange={(updated) =>
                patchPlan((p) => ({ ...p, steps: p.steps.map((x) => (x.id === updated.id ? updated : x)) }))
              }
            />
          ))}
        </ul>
      </div>

      <div className="plan-actions">
        <button type="button" className="btn btn-sm btn-accent" onClick={() => void copyExport()}>
          Copy cut list
        </button>
        {editor && (
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void generate()}>
            {busy ? "Starting…" : "Rebuild the plan"}
          </button>
        )}
      </div>
    </div>
  );
}

function CutRow({
  episodeId,
  item,
  editor,
  onChange,
}: {
  episodeId: string;
  item: CutItemView;
  editor: boolean;
  onChange: (i: CutItemView) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [start, setStart] = useState(toSeconds(item.edited_start_ms ?? item.start_ms));
  const [end, setEnd] = useState(toSeconds(item.edited_end_ms ?? item.end_ms));
  const [busy, setBusy] = useState(false);

  async function send(body: { decision?: Decision; start_ms?: number; end_ms?: number }) {
    setBusy(true);
    try {
      onChange(await decideCut(episodeId, item.id, body));
      setEditing(false);
    } catch (e) {
      toast.push(errorToast(e, "Couldn't update the cut"));
    } finally {
      setBusy(false);
    }
  }

  function saveEdit(e: FormEvent) {
    e.preventDefault();
    void send({ start_ms: fromSeconds(start), end_ms: fromSeconds(end) });
  }

  const from = item.edited_start_ms ?? item.start_ms;
  const to = item.edited_end_ms ?? item.end_ms;
  const edited = item.edited_start_ms !== null || item.edited_end_ms !== null;

  return (
    <li className={`cut cut-${item.decision} cut-${item.source}`}>
      <div className="cut-head">
        <span className={`cut-source cut-source-${item.source}`}>
          {item.source === "human" ? "⚑ flagged" : `model · ${Math.round((item.confidence ?? 0) * 100)}%`}
        </span>
        <span className="cut-time">
          {fmtTimeMs(from)} – {fmtTimeMs(to)}
          {edited && <s> {fmtTimeMs(item.start_ms)} – {fmtTimeMs(item.end_ms)}</s>}
        </span>
        <span className={`cut-decision cut-decision-${item.decision}`}>{item.decision}</span>
      </div>
      <p className="cut-quote">{item.quote ? `“${item.quote}”` : <em>no transcript text here</em>}</p>
      {item.reason && <p className="cut-reason">{item.reason}</p>}
      {editor && (
        <div className="cut-actions">
          <button
            type="button"
            className={`btn btn-sm${item.decision === "accepted" ? " btn-green" : ""}`}
            disabled={busy}
            onClick={() => void send({ decision: item.decision === "accepted" ? "pending" : "accepted" })}
          >
            {item.decision === "accepted" ? "Accepted" : "Accept"}
          </button>
          <button
            type="button"
            className={`btn btn-sm${item.decision === "rejected" ? " btn-danger" : ""}`}
            disabled={busy}
            onClick={() => void send({ decision: item.decision === "rejected" ? "pending" : "rejected" })}
          >
            {item.decision === "rejected" ? "Rejected" : "Reject"}
          </button>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => setEditing((v) => !v)}>
            {editing ? "Cancel" : "Edit span"}
          </button>
        </div>
      )}
      {editing && (
        <form className="cut-edit" onSubmit={saveEdit}>
          <label>
            from (s)
            <input type="number" step="0.1" min="0" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            to (s)
            <input type="number" step="0.1" min="0" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-sm btn-accent" disabled={busy}>
            Save
          </button>
        </form>
      )}
    </li>
  );
}

function ColdCard({
  episodeId,
  cold,
  editor,
  onChange,
}: {
  episodeId: string;
  cold: ColdOpenView;
  editor: boolean;
  onChange: (c: ColdOpenView) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function pick() {
    setBusy(true);
    try {
      onChange(await pickColdOpen(episodeId, cold.id, !cold.picked));
    } catch (e) {
      toast.push(errorToast(e, "Couldn't pick the cold open"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className={`cold${cold.picked ? " cold-picked" : ""}`}>
      <div className="cut-head">
        <span className="cut-time">
          {fmtTimeMs(cold.start_ms)} – {fmtTimeMs(cold.end_ms)}
        </span>
        <span className="cut-source">{Math.round((cold.confidence ?? 0) * 100)}%</span>
        {cold.picked && <span className="cut-decision cut-decision-accepted">picked</span>}
      </div>
      <p className="cut-quote">“{cold.quote}”</p>
      {cold.why && <p className="cut-reason">{cold.why}</p>}
      {editor && (
        <div className="cut-actions">
          <button type="button" className={`btn btn-sm${cold.picked ? " btn-green" : " btn-accent"}`} disabled={busy} onClick={() => void pick()}>
            {cold.picked ? "Picked" : "Pick this one"}
          </button>
        </div>
      )}
    </li>
  );
}

function StepRow({
  episodeId,
  step,
  editor,
  onChange,
}: {
  episodeId: string;
  step: StepView;
  editor: boolean;
  onChange: (s: StepView) => void;
}) {
  const toast = useToast();
  async function toggle(done: boolean) {
    try {
      onChange(await tickStep(episodeId, step.id, done));
    } catch (e) {
      toast.push(errorToast(e, "Couldn't update the checklist"));
    }
  }
  return (
    <li className={`step-row${step.done_at ? " step-row-done" : ""}`}>
      <label>
        <input type="checkbox" checked={!!step.done_at} disabled={!editor} onChange={(e) => void toggle(e.target.checked)} />
        <span>{step.label}</span>
      </label>
    </li>
  );
}
