import { useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { changeStage, type Stage } from "../api/episodes";
import { type Move, movesFrom, PIPELINE, STAGE_LABEL } from "../domain/workflow";
import { type Episode, useEpisodes } from "../state/episodes";
import { useMe } from "../state/session";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

const BUTTON_LABEL = (m: Move) => {
  switch (m.kind) {
    case "block":
      return "Mark blocked";
    case "unblock":
      return `Unblock → ${STAGE_LABEL[m.to]}`;
    case "back":
      return `Back to ${STAGE_LABEL[m.to].toLowerCase()}`;
    default:
      return m.to === "published" ? "Mark published" : `Move to ${STAGE_LABEL[m.to].toLowerCase()}`;
  }
};

export function StagePanel({ episode, onMoved }: { episode: Episode; onMoved: () => void }) {
  const me = useMe();
  const { patch } = useEpisodes();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<Stage | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const stage = episode.stage;

  async function move(to: Stage) {
    if (busy) return;
    setBusy(to);
    setError(null);
    try {
      const summary = await changeStage(episode.id, to, reason.trim() || null);
      patch(summary, { stage: to });
      setReason("");
      toast.push({ kind: "success", title: `Moved to ${STAGE_LABEL[to].toLowerCase()}` });
      onMoved();
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setBusy(null);
    }
  }

  if (stage === null) {
    return (
      <Banner kind="error">
        <ErrorDetail
          error={episode.historyError ?? { name: "ApiError", status: 0, detail: "Stage unknown.", traceId: null, retryable: true }}
          lead="Couldn't work out which stage this episode is in."
          onRetry={onMoved}
        />
      </Banner>
    );
  }

  // Publishing goes through approval in the Publish panel; the server refuses it here.
  const moves = movesFrom(stage, me.role).filter((m) => m.to !== "published");
  const currentIndex = PIPELINE.indexOf(stage);

  return (
    <>
      <ol className={`stepper${stage === "blocked" ? " stepper-blocked" : ""}`}>
        {PIPELINE.map((s, i) => {
          const state =
            stage === "blocked" ? "off" : i < currentIndex ? "done" : i === currentIndex ? "now" : "next";
          return (
            <li key={s} className={`step step-${state}`} aria-current={state === "now" ? "step" : undefined}>
              <span className="step-bar" />
              <span className="step-label">{STAGE_LABEL[s]}</span>
            </li>
          );
        })}
      </ol>

      {stage === "blocked" && (
        <Banner kind="warn">
          This episode is blocked. Unblock it into whichever stage the work resumes from.
        </Banner>
      )}

      {stage === "published" ? (
        <p className="panel-empty">Published is final. Nothing moves from here.</p>
      ) : (
        <div className="moves">
          <label className="field">
            <span>Reason (optional, recorded with the move)</span>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={stage === "blocked" ? "e.g. final mix landed" : "e.g. waiting on Albert's mix"}
              maxLength={500}
            />
          </label>
          <div className="move-buttons">
            {moves.map((m) => (
              <button
                key={m.to}
                type="button"
                className={`btn${m.kind === "forward" || m.kind === "unblock" ? " btn-accent" : ""}${m.kind === "block" ? " btn-quiet" : ""}`}
                disabled={!m.allowed || busy !== null}
                title={m.why ?? undefined}
                onClick={() => void move(m.to)}
              >
                {busy === m.to ? "Moving…" : BUTTON_LABEL(m)}
              </button>
            ))}
          </div>
          {moves.some((m) => !m.allowed) && (
            <p className="moves-note">
              {moves
                .filter((m) => !m.allowed)
                .map((m) => m.why)
                .join(" ")}
            </p>
          )}
          {stage === "review" && (
            <p className="moves-note">Publishing happens in the Publish panel below, once the owner approves the pack.</p>
          )}
          {error && (
            <Banner kind="error">
              <ErrorDetail error={error} lead="The move was refused." />
            </Banner>
          )}
        </div>
      )}
    </>
  );
}
