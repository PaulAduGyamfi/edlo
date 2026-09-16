import { useEffect, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { approveEpisode, generatePack, getPack, type JobView, type PackView } from "../api/episodes";
import { useJob } from "../hooks/useJob";
import { fmtTime } from "../lib/time";
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
  | { status: "ready"; pack: PackView };

const RULE_LABEL: Record<string, string> = {
  invented_link: "Link not on the allowlist",
  unverified_sponsor: "Sponsor never mentioned in the episode",
  chapters_not_monotonic: "Chapters are out of order",
};

/** The pack the model drafted, the policy check, and the owner's approval. */
export function PublishPanel({ episode }: { episode: Episode }) {
  const me = useMe();
  const toast = useToast();
  const { reload } = useEpisodes();
  const editor = me.role !== "audio_editor";
  const owner = me.role === "owner";
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPack(episode.id).then(
      (data) => {
        if (cancelled) return;
        if ("job" in data) setState({ status: "pending", job: data.job });
        else setState({ status: "ready", pack: data });
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
    if (job.status === "succeeded") refresh();
  });

  async function draft() {
    setBusy(true);
    setRefused(null);
    try {
      await generatePack(episode.id);
      refresh();
    } catch (e) {
      toast.push(errorToast(e, "Couldn't start the draft"));
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    setRefused(null);
    try {
      await approveEpisode(episode.id);
      toast.push({ kind: "success", title: `Published “${episode.title}”` });
      void reload();
      refresh();
    } catch (e) {
      // A 422 stores its violations on the pack; show them from the source.
      setRefused(toApiError(e));
      refresh();
    } finally {
      setBusy(false);
    }
  }

  if (episode.stage === "published") {
    return <p className="panel-empty">Published. The pack below is what went out.</p>;
  }
  if (state.status === "loading") {
    return (
      <p className="panel-empty" aria-busy="true">
        Loading…
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <Banner kind="error">
        <ErrorDetail error={state.error} lead="Couldn't load the publishing pack." onRetry={refresh} />
      </Banner>
    );
  }
  if (state.status === "none") {
    return (
      <div className="plan-empty">
        <p className="panel-empty">No publishing pack yet. The model drafts the copy from the transcript; policy checks it; the owner approves.</p>
        {editor && (
          <button type="button" className="btn btn-accent" disabled={busy} onClick={() => void draft()}>
            {busy ? "Starting…" : "Draft the pack"}
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
          <strong>The draft failed.</strong> {job.user_message ?? "Something went wrong in the background."}
        </Banner>
      );
    }
    return (
      <div className="tx-pending" role="status" aria-busy="true">
        <span className="tx-pending-dot" aria-hidden="true" />
        <div>
          <strong>{job.status === "running" ? "Drafting the pack…" : "Waiting for a worker…"}</strong>
          <span className="tx-pending-sub">You can close this tab.</span>
        </div>
      </div>
    );
  }

  const { pack } = state;
  const inReview = episode.stage === "review";
  return (
    <div className="pack">
      {pack.status === "ai_disabled" && (
        <Banner kind="info">AI is turned off: the pack is the title alone. Approval still works.</Banner>
      )}
      {pack.violations.length > 0 && (
        <Banner kind="error">
          <strong>Policy blocked this pack.</strong>
          <ul className="violations">
            {pack.violations.map((v, i) => (
              <li key={i}>
                {RULE_LABEL[v.rule] ?? v.rule}
                {v.detail ? `: ${v.detail}` : ""}
              </li>
            ))}
          </ul>
          Redraft, or fix the transcript it was drafted from.
        </Banner>
      )}
      {refused && pack.violations.length === 0 && (
        <Banner kind="error">
          <ErrorDetail error={refused} lead="Approval was refused." />
        </Banner>
      )}
      <dl className="pack-fields">
        <dt>Title</dt>
        <dd>{pack.title}</dd>
        <dt>Description</dt>
        <dd className="pack-description">{pack.description || <em>none</em>}</dd>
        <dt>Chapters</dt>
        <dd>
          {pack.chapters.length ? (
            <ol className="chapters">
              {pack.chapters.map((c, i) => (
                <li key={i}>
                  <span className="cut-time">{fmtTime(c.start_ms)}</span> {c.title}
                </li>
              ))}
            </ol>
          ) : (
            <em>none</em>
          )}
        </dd>
        <dt>Links</dt>
        <dd>{pack.links.length ? pack.links.join(", ") : <em>none</em>}</dd>
        <dt>Sponsors</dt>
        <dd>{pack.sponsors.length ? pack.sponsors.join(", ") : <em>none</em>}</dd>
      </dl>
      <div className="plan-actions">
        {owner && (
          <button
            type="button"
            className="btn btn-green"
            disabled={busy || !inReview || pack.violations.length > 0}
            title={inReview ? undefined : "Approval opens when the episode is in review."}
            onClick={() => void approve()}
          >
            {busy ? "…" : "Approve and publish"}
          </button>
        )}
        {editor && (
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void draft()}>
            Redraft
          </button>
        )}
        {!inReview && <span className="moves-note">Approval opens when the episode is in review.</span>}
      </div>
    </div>
  );
}
